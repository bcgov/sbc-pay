# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Service to manage CFS EFT Payments."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from flask import current_app
from sqlalchemy import and_, func

from pay_api.exceptions import BusinessException
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTCreditInvoiceLink as EFTCreditInvoiceLinkModel
from pay_api.models import EFTShortnameLinks as EFTShortnameLinksModel
from pay_api.models import EFTShortnamesHistorical as EFTHistoryModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import RefundPartialLine, db
from pay_api.models import Statement as StatementModel
from pay_api.models import StatementInvoices as StatementInvoicesModel
from pay_api.utils.enums import (
    CfsAccountStatus,
    EFTCreditInvoiceStatus,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    PaymentSystem,
)
from pay_api.utils.errors import Error
from pay_api.utils.user_context import user_context

from .auth import get_account_admin_users
from .deposit_service import DepositService
from .eft_refund import EFTRefund as EFTRefundService
from .eft_short_name_historical import EFTShortnameHistorical as EFTHistoryService
from .eft_short_name_historical import EFTShortnameHistory as EFTHistory
from .email_service import _render_payment_reversed_template, send_email_async
from .invoice import Invoice  # noqa: TC001
from .invoice_reference import InvoiceReference  # noqa: TC001
from .partner_disbursements import PartnerDisbursements
from .payment_account import PaymentAccount  # noqa: TC001
from .payment_line_item import PaymentLineItem  # noqa: TC001
from .statement import Statement as StatementService


class EftService(DepositService):
    """Service to manage electronic fund transfers."""

    def get_payment_method_code(self):
        """Return EFT as the payment method code."""
        return PaymentMethod.EFT.value

    def get_payment_system_code(self):
        """Return PAYBC as the system code."""
        return PaymentSystem.PAYBC.value

    def create_account(
        self,
        identifier: str,  # noqa: ARG002
        contact_info: dict[str, Any],  # noqa: ARG002
        payment_info: dict[str, Any],  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ) -> CfsAccountModel:
        """Create an account for the EFT transactions."""
        # Create CFS Account model instance, set the status as PENDING
        current_app.logger.info(f"Creating EFT account details in PENDING status for {identifier}")
        cfs_account = CfsAccountModel()
        cfs_account.status = CfsAccountStatus.PENDING.value
        cfs_account.payment_method = PaymentMethod.EFT.value
        return cfs_account

    def create_invoice(
        self,
        payment_account: PaymentAccount,  # noqa: ARG002
        line_items: list[PaymentLineItem],  # noqa: ARG002
        invoice: Invoice,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ) -> None:
        """Do nothing here, we create invoice references on the create CFS_INVOICES job."""
        self.ensure_no_payment_blockers(payment_account)
        PartnerDisbursements.handle_payment(invoice)

    def complete_post_invoice(self, invoice: Invoice, invoice_reference: InvoiceReference) -> None:  # noqa: ARG002
        """Complete any post invoice activities if needed."""
        # Publish message to the queue with payment token, so that they can release records on their side.
        self.release_payment_or_reversal(invoice=invoice)

    def get_default_invoice_status(self) -> str:
        """Return the default status for invoice when created."""
        return InvoiceStatus.APPROVED.value

    def create_payment(
        self,
        payment_account: PaymentAccountModel,  # noqa: ARG002
        invoice: InvoiceModel,  # noqa: ARG002
        payment_date: datetime,  # noqa: ARG002
        paid_amount,
    ) -> PaymentModel:
        """Create a payment record for an invoice."""
        payment = PaymentModel(
            payment_method_code=self.get_payment_method_code(),
            payment_status_code=PaymentStatus.COMPLETED.value,
            payment_system_code=self.get_payment_system_code(),
            invoice_number=f"{current_app.config['EFT_INVOICE_PREFIX']}{invoice.id}",
            invoice_amount=invoice.total,
            payment_account_id=payment_account.id,
            payment_date=payment_date,
            paid_amount=paid_amount,
            receipt_number=invoice.id,
        )
        return payment

    def process_cfs_refund(
        self,
        invoice: InvoiceModel,  # noqa: ARG002
        payment_account: PaymentAccount,  # noqa: ARG002
        refund_partial: list[RefundPartialLine],  # noqa: ARG002
    ):
        """Process refund in CFS."""
        is_partial = bool(refund_partial)

        if not is_partial:
            PartnerDisbursements.handle_reversal(invoice)

        cils = EFTCreditInvoiceLinkModel.find_by_invoice_id(invoice.id)
        # 1. Possible to have no CILs and no invoice_reference, nothing to reverse.
        if (
            invoice.invoice_status_code == InvoiceStatus.APPROVED.value
            and InvoiceReferenceModel.find_by_invoice_id_and_status(invoice.id, InvoiceReferenceStatus.ACTIVE.value)
            is None
            and not cils
        ):
            return InvoiceStatus.CANCELLED.value
        inv_ref = InvoiceReferenceModel.find_by_invoice_id_and_status(
            invoice.id, InvoiceReferenceStatus.COMPLETED.value
        )
        if inv_ref and inv_ref.is_consolidated:
            # We can't allow these, because they credit memo the account and don't actually refund.
            # Also untested with EFT. We want to be able to refund back to the original payment method.
            raise BusinessException(Error.INVALID_CONSOLIDATED_REFUND)

        if is_partial:
            if inv_ref is None or any(cil.status_code != EFTCreditInvoiceStatus.COMPLETED.value for cil in cils):
                raise BusinessException(Error.EFT_PARTIAL_REFUND)

        invoice_status = EFTRefundService.handle_invoice_refund(invoice, payment_account, cils, is_partial)
        if is_partial:
            invoice_status = super()._refund_and_create_credit_memo(
                invoice=invoice, refund_partial=refund_partial, send_credit_notification=False
            )
        return invoice_status

    @staticmethod
    def create_invoice_reference(
        invoice: InvoiceModel, invoice_number: str, reference_number: str
    ) -> InvoiceReferenceModel:
        """Create an invoice reference record."""
        if not (invoice_reference := InvoiceReferenceModel.find_any_active_reference_by_invoice_number(invoice_number)):
            invoice_reference = InvoiceReferenceModel()

        invoice_reference.invoice_id = invoice.id
        invoice_reference.invoice_number = invoice_number
        invoice_reference.reference_number = reference_number
        invoice_reference.status_code = InvoiceReferenceStatus.ACTIVE.value

        return invoice_reference

    @staticmethod
    def create_receipt(invoice: InvoiceModel, payment: PaymentModel) -> ReceiptModel:
        """Create a receipt record for an invoice payment."""
        receipt = ReceiptModel(
            receipt_date=payment.payment_date,
            receipt_amount=payment.paid_amount,
            invoice_id=invoice.id,
            receipt_number=payment.receipt_number,
        )
        return receipt

    @staticmethod
    def apply_payment_action(short_name_id: int, auth_account_id: str, statement_id: int = None):
        """Apply EFT payments to outstanding payments."""
        current_app.logger.debug("<apply_payment_action")
        if (auth_account_id is None) or (
            payment_account := PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        ) is None:
            raise BusinessException(Error.EFT_PAYMENT_ACTION_ACCOUNT_ID_REQUIRED)

        if (
            statement_id is not None
            and StatementModel.find_statement_by_account(payment_account.id, statement_id) is None
        ):
            raise BusinessException(Error.EFT_PAYMENT_ACTION_STATEMENT_ID_INVALID)

        EftService.process_owing_statements(
            short_name_id=short_name_id, auth_account_id=auth_account_id, statement_id=statement_id
        )
        current_app.logger.debug(">apply_payment_action")

    @staticmethod
    def cancel_payment_action(
        short_name_id: int, auth_account_id: str, invoice_id: int = None, statement_id: int = None
    ):
        """Cancel EFT pending payments."""
        current_app.logger.debug("<cancel_payment_action")
        if any(
            [
                auth_account_id is None,
                (payment_account := PaymentAccountModel.find_by_auth_account_id(auth_account_id)) is None,
            ]
        ):
            raise BusinessException(Error.EFT_PAYMENT_ACTION_ACCOUNT_ID_REQUIRED)

        credit_links = EftService._get_shortname_invoice_links(
            short_name_id=short_name_id,
            payment_account_id=payment_account.id,
            invoice_id=invoice_id,
            statuses=[EFTCreditInvoiceStatus.PENDING.value],
            statement_id=statement_id,
        )
        link_group_ids = set()
        for credit_link in credit_links:
            eft_credit = EFTRefundService.return_eft_credit(
                eft_credit_link=credit_link,
                refund_amount=credit_link.amount,
                update_status=EFTCreditInvoiceStatus.CANCELLED.value,
            )
            if credit_link.link_group_id:
                link_group_ids.add(credit_link.link_group_id)
            db.session.add(eft_credit)
            db.session.add(credit_link)

        # Clean up pending historical records from pending links
        for link_group_id in link_group_ids:
            history_model = EFTHistoryModel.find_by_related_group_link_id(link_group_id)
            if history_model:
                db.session.delete(history_model)

        db.session.flush()
        current_app.logger.debug(">cancel_payment_action")

    @staticmethod
    def reverse_payment_action(short_name_id: int, statement_id: int):
        """Reverse EFT Payments on a statement to short name EFT credits."""
        current_app.logger.debug("<reverse_payment_action")
        if statement_id is None:
            raise BusinessException(Error.EFT_PAYMENT_ACTION_STATEMENT_ID_REQUIRED)

        credit_invoice_links = EftService.get_statement_credit_invoice_links(short_name_id, statement_id)
        EftService._validate_reversal_credit_invoice_links(statement_id, credit_invoice_links)

        alt_flow_invoice_statuses = [
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceStatus.REFUNDED.value,
            InvoiceStatus.CANCELLED.value,
        ]
        link_group_id = EFTCreditInvoiceLinkModel.get_next_group_link_seq()
        reversed_credits = 0
        invoice_disbursements = {}
        for current_link in credit_invoice_links:
            invoice = InvoiceModel.find_by_id(current_link.invoice_id)

            # Check if the invoice status is handled by other flows and can be skipped
            if invoice.invoice_status_code in alt_flow_invoice_statuses:
                continue

            if invoice.invoice_status_code != InvoiceStatus.PAID.value:
                current_app.logger.error(
                    f"EFT Invoice Payment could not be reversed for invoice "
                    f"- {invoice.id} in status {invoice.invoice_status_code}."
                )
                raise BusinessException(Error.EFT_PAYMENT_INVOICE_REVERSE_UNEXPECTED_STATUS)

            eft_credit = EFTRefundService.return_eft_credit(
                eft_credit_link=current_link, refund_amount=current_link.amount
            )
            eft_credit.flush()
            reversed_credits += current_link.amount

            EFTCreditInvoiceLinkModel(
                eft_credit_id=eft_credit.id,
                status_code=EFTCreditInvoiceStatus.PENDING_REFUND.value,
                amount=current_link.amount,
                receipt_number=current_link.receipt_number,
                invoice_id=invoice.id,
                link_group_id=link_group_id,
            ).flush()

            if corp_type := CorpTypeModel.find_by_code(invoice.corp_type_code):
                if corp_type.has_partner_disbursements and current_link.amount > 0:
                    invoice_disbursements.setdefault(invoice, 0)
                    invoice_disbursements[invoice] += current_link.amount

        for invoice, total_amount in invoice_disbursements.items():
            if total_amount != invoice.total:
                raise BusinessException(Error.EFT_PARTIAL_REFUND)
            PartnerDisbursements.handle_reversal(invoice)

        statement = StatementModel.find_by_id(statement_id)
        EFTHistoryService.create_statement_reverse(
            EFTHistory(
                short_name_id=short_name_id,
                amount=reversed_credits,
                credit_balance=EFTCreditModel.get_eft_credit_balance(short_name_id),
                payment_account_id=statement.payment_account_id,
                related_group_link_id=link_group_id,
                statement_number=statement_id,
                hidden=False,
                is_processing=True,
            )
        ).flush()

        EftService._send_reversed_payment_notification(statement, reversed_credits)
        current_app.logger.debug(">reverse_payment_action")

    @staticmethod
    def get_pending_payment_count():
        """Get count of pending EFT Credit Invoice Links."""
        return (
            db.session.query(db.func.count(InvoiceModel.id).label("invoice_count"))
            .join(
                EFTCreditInvoiceLinkModel,
                EFTCreditInvoiceLinkModel.invoice_id == InvoiceModel.id,
            )
            .filter(InvoiceModel.payment_account_id == PaymentAccountModel.id)
            .filter(EFTCreditInvoiceLinkModel.status_code.in_([EFTCreditInvoiceStatus.PENDING.value]))
            .correlate(PaymentAccountModel)
            .scalar_subquery()
        )

    @staticmethod
    def _get_shortname_invoice_links(
        short_name_id: int,  # noqa: ARG002
        payment_account_id: int,  # noqa: ARG002
        statuses: list[str],  # noqa: ARG002
        invoice_id: int = None,  # noqa: ARG002
        statement_id: int = None,  # noqa: ARG002
    ) -> list[EFTCreditInvoiceLinkModel]:
        """Get short name credit invoice links by account."""
        credit_links_query = (
            db.session.query(EFTCreditInvoiceLinkModel)
            .join(
                EFTCreditModel,
                EFTCreditModel.id == EFTCreditInvoiceLinkModel.eft_credit_id,
            )
            .join(InvoiceModel, InvoiceModel.id == EFTCreditInvoiceLinkModel.invoice_id)
            .join(StatementInvoicesModel, StatementInvoicesModel.invoice_id == EFTCreditInvoiceLinkModel.invoice_id)
            .filter(InvoiceModel.payment_account_id == payment_account_id)
            .filter(EFTCreditModel.short_name_id == short_name_id)
            .filter(EFTCreditInvoiceLinkModel.status_code.in_(statuses))
        )
        credit_links_query = credit_links_query.filter_conditionally(statement_id, StatementInvoicesModel.statement_id)
        credit_links_query = credit_links_query.filter_conditionally(invoice_id, InvoiceModel.id)
        return credit_links_query.all()

    @staticmethod
    @user_context
    def _send_reversed_payment_notification(statement: StatementModel, reversed_amount: Decimal, **kwargs):  # noqa: ARG004
        payment_account = PaymentAccountModel.find_by_id(statement.payment_account_id)
        summary_dict: dict = StatementService.get_summary(payment_account.auth_account_id)

        due_date = StatementService.calculate_due_date(statement.to_date)
        outstanding_balance = Decimal(str(summary_dict["total_due"])) + reversed_amount
        email_params = {
            "accountId": payment_account.auth_account_id,
            "accountName": payment_account.name,
            "reversedAmount": f"{reversed_amount:,.2f}",
            "outstandingBalance": f"{outstanding_balance:,.2f}",
            "statementMonth": statement.from_date.strftime("%B"),
            "statementNumber": statement.id,
            "dueDate": datetime.fromisoformat(due_date).strftime("%B %e, %Y"),
        }

        org_admins_response = get_account_admin_users(payment_account.auth_account_id)
        admins = org_admins_response.get("members") if org_admins_response.get("members", None) else []
        recipients = [
            admin["user"]["contacts"][0]["email"]
            for admin in admins
            if "user" in admin and "contacts" in admin["user"] and admin["user"]["contacts"]
        ]

        send_email_async(
            recipients=recipients,
            subject="Outstanding Balance Adjustment Notice",
            body=_render_payment_reversed_template(email_params),
        )

    @staticmethod
    def _validate_reversal_credit_invoice_links(
        statement_id: int, credit_invoice_links: list[EFTCreditInvoiceLinkModel]
    ):
        """Validate credit invoice links for reversal."""
        invalid_link_statuses = [
            EFTCreditInvoiceStatus.PENDING.value,
            EFTCreditInvoiceStatus.PENDING_REFUND.value,
            EFTCreditInvoiceStatus.REFUNDED.value,
        ]

        # We are reversing all invoices associated to a statement, if any links are in transition state or already
        # refunded we should not allow a statement reversal
        unprocessable_links = [link for link in credit_invoice_links if link.status_code in invalid_link_statuses]
        if unprocessable_links:
            raise BusinessException(Error.EFT_PAYMENT_ACTION_CREDIT_LINK_STATUS_INVALID)
        # Validate when statement paid date can't be older than 60 days
        min_payment_date = (
            db.session.query(func.min(InvoiceModel.payment_date))
            .join(
                StatementInvoicesModel,
                StatementInvoicesModel.invoice_id == InvoiceModel.id,
            )
            .filter(StatementInvoicesModel.statement_id == statement_id)
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value)
            .scalar()
        )

        if min_payment_date is None:
            raise BusinessException(Error.EFT_PAYMENT_ACTION_UNPAID_STATEMENT)

        date_difference = datetime.now(tz=UTC) - min_payment_date.replace(tzinfo=UTC)
        if date_difference.days > 60:
            raise BusinessException(Error.EFT_PAYMENT_ACTION_REVERSAL_EXCEEDS_SIXTY_DAYS)

    @staticmethod
    def get_statement_credit_invoice_links(shortname_id, statement_id) -> list[EFTCreditInvoiceLinkModel]:
        """Get most recent EFT Credit invoice links associated to a statement and short name."""
        max_link_group_id_subquery = (
            db.session.query(
                EFTCreditInvoiceLinkModel.invoice_id,
                func.max(EFTCreditInvoiceLinkModel.link_group_id).label("max_link_group_id"),
            )
            .group_by(EFTCreditInvoiceLinkModel.invoice_id)
            .subquery()
        )

        query = (
            db.session.query(EFTCreditInvoiceLinkModel)
            .join(
                EFTCreditModel,
                EFTCreditModel.id == EFTCreditInvoiceLinkModel.eft_credit_id,
            )
            .join(
                StatementInvoicesModel,
                StatementInvoicesModel.invoice_id == EFTCreditInvoiceLinkModel.invoice_id,
            )
            .join(
                max_link_group_id_subquery,
                and_(
                    EFTCreditInvoiceLinkModel.invoice_id == max_link_group_id_subquery.c.invoice_id,
                    EFTCreditInvoiceLinkModel.link_group_id == max_link_group_id_subquery.c.max_link_group_id,
                ),
            )
            .filter(StatementInvoicesModel.statement_id == statement_id)
            .filter(EFTCreditModel.short_name_id == shortname_id)
            .filter(EFTCreditInvoiceLinkModel.status_code != EFTCreditInvoiceStatus.CANCELLED.value)
            .order_by(
                EFTCreditInvoiceLinkModel.invoice_id.desc(),
                EFTCreditInvoiceLinkModel.created_on.desc(),
                EFTCreditInvoiceLinkModel.id.desc(),
            )
        )
        return query.all()

    @staticmethod
    def apply_eft_credit(invoice_id: int, short_name_id: int, link_group_id: int, auto_save: bool = False):
        """Apply EFT credit and update remaining credit records."""
        invoice = InvoiceModel.find_by_id(invoice_id)
        payment_account = PaymentAccountModel.find_by_id(invoice.payment_account_id)

        # Clear any existing pending credit links on this invoice
        EftService.cancel_payment_action(short_name_id, payment_account.auth_account_id, invoice_id)

        eft_credit_balance = EFTCreditModel.get_eft_credit_balance(short_name_id)
        invoice_balance = invoice.total - (invoice.paid or 0)

        if eft_credit_balance < invoice_balance:
            return

        eft_credits = EFTCreditModel.get_eft_credits(short_name_id)
        for eft_credit in eft_credits:
            credit_invoice_link = EFTCreditInvoiceLinkModel(
                eft_credit_id=eft_credit.id,
                status_code=EFTCreditInvoiceStatus.PENDING.value,
                invoice_id=invoice.id,
                link_group_id=link_group_id,
            )

            if eft_credit.remaining_amount >= invoice_balance:
                # Credit covers the full invoice balance
                credit_invoice_link.amount = invoice_balance
                credit_invoice_link.save_or_add(auto_save)
                eft_credit.remaining_amount -= invoice_balance
                eft_credit.save_or_add(auto_save)
                invoice_balance = 0
                break

            # Credit covers partial invoice balance
            invoice_balance -= eft_credit.remaining_amount
            credit_invoice_link.amount = eft_credit.remaining_amount
            credit_invoice_link.save_or_add(auto_save)
            eft_credit.remaining_amount = 0
            eft_credit.save_or_add(auto_save)

        if invoice_balance == 0:
            PartnerDisbursements.handle_payment(invoice)

    @staticmethod
    def process_owing_statements(
        short_name_id: int, auth_account_id: str, is_new_link: bool = False, statement_id: int = None
    ):
        """Process outstanding statement invoices for an EFT Short name."""
        current_app.logger.debug("<process_owing_statements")

        if EFTShortnameLinksModel.find_active_link(short_name_id, auth_account_id) is None:
            raise BusinessException(Error.EFT_SHORT_NAME_NOT_LINKED)

        credit_balance = EFTCreditModel.get_eft_credit_balance(short_name_id)
        summary_dict: dict = StatementService.get_summary(auth_account_id=auth_account_id, statement_id=statement_id)
        total_due = Decimal(str(summary_dict["total_due"]))

        if credit_balance < total_due:
            if not is_new_link:
                raise BusinessException(Error.EFT_INSUFFICIENT_CREDITS)
            return

        statements, _ = StatementService.get_account_statements(
            auth_account_id=auth_account_id, page=1, limit=1000, is_owing=True, statement_id=statement_id
        )
        link_groups = {}
        if statements:
            for statement in statements:
                link_group_id = EFTCreditInvoiceLinkModel.get_next_group_link_seq()
                invoices = EftService._get_statement_invoices_owing(auth_account_id, statement.id)
                for invoice in invoices:
                    if invoice.payment_method_code == PaymentMethod.EFT.value:
                        link_groups[invoice.id] = link_group_id

                if invoices:
                    credit_balance -= statement.amount_owing
                    EFTHistoryService.create_statement_paid(
                        EFTHistory(
                            short_name_id=short_name_id,
                            amount=statement.amount_owing,
                            credit_balance=credit_balance,
                            payment_account_id=statement.payment_account_id,
                            related_group_link_id=link_group_id,
                            statement_number=statement.id,
                            hidden=True,
                            is_processing=True,
                        )
                    ).flush()

        for invoice_id, group_id in link_groups.items():
            EftService.apply_eft_credit(invoice_id, short_name_id, group_id)

        current_app.logger.debug(">process_owing_statements")

    @staticmethod
    def _get_statement_invoices_owing(auth_account_id: str, statement_id: int = None) -> list[InvoiceModel]:
        """Return statement invoices that have not been fully paid."""
        unpaid_status = (
            InvoiceStatus.PARTIAL.value,
            InvoiceStatus.APPROVED.value,
            InvoiceStatus.OVERDUE.value,
        )
        query = (
            db.session.query(InvoiceModel)
            .join(
                PaymentAccountModel,
                and_(
                    PaymentAccountModel.id == InvoiceModel.payment_account_id,
                    PaymentAccountModel.auth_account_id == auth_account_id,
                ),
            )
            .join(
                StatementInvoicesModel,
                StatementInvoicesModel.invoice_id == InvoiceModel.id,
            )
            .filter(InvoiceModel.invoice_status_code.in_(unpaid_status))
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value)
        )

        query = query.filter_conditionally(statement_id, StatementInvoicesModel.statement_id)
        query = query.order_by(InvoiceModel.created_on.asc())

        return query.all()
