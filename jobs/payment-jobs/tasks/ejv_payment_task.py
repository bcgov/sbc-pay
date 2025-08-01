# Copyright © 2019 Province of British Columbia
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
"""Task to create Journal Voucher for gov account payments."""

import time
from dataclasses import dataclass
from typing import List

from flask import current_app
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import EjvLink as EjvLinkModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import RefundsPartial as RefundsPartialModel
from pay_api.models import db
from pay_api.utils.enums import (
    DisbursementStatus,
    EjvFileType,
    EJVLinkType,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    RefundsPartialStatus,
    RefundsPartialType,
)
from pay_api.utils.util import generate_transaction_number

from tasks.common.cgi_ejv import CgiEjv
from tasks.common.dataclasses import EjvTransaction, TransactionLineItem


@dataclass
class JVParams:
    """Data class for JV parameters."""

    batch_type: str
    effective_date: str
    journal_name: str
    debit_distribution: str
    account_jv: str
    control_total: int
    total: float
    line_number: int
    payment_desc: str


class EjvPaymentTask(CgiEjv):
    """Task to create Journal Voucher for gov account payments."""

    @classmethod
    def create_ejv_file(cls):
        """Create JV files and upload to CGI.

        Steps:
        1. Find all accounts for GI or GA.
        2. Find outstanding invoices and partial refunds for payment.
        3. Group by account and create JD for each service fee and filing fee.
        4. Upload the file to minio for future reference.
        5. Upload to sftp for processing. First upload JV file and then a TRG file.
        6. Update the statuses and create records to for the batch.
        """
        cls._create_ejv_file_for_gov_account(batch_type="GI")
        cls._create_ejv_file_for_gov_account(batch_type="GA")

    @classmethod
    def _create_ejv_file_for_gov_account(cls, batch_type: str):  # pylint:disable=too-many-locals, too-many-statements
        """Create EJV file for the partner and upload."""
        ejv_content: str = ""
        batch_total: float = 0
        control_total: int = 0

        file_name = cls.get_file_name()
        ejv_file_model: EjvFileModel = EjvFileModel(
            file_type=EjvFileType.PAYMENT.value,
            file_ref=file_name,
            disbursement_status_code=DisbursementStatus.UPLOADED.value,
        ).flush()
        current_app.logger.info(f"Creating EJV File Id: {ejv_file_model.id}, File Name: {file_name}")
        batch_number = cls.get_batch_number(ejv_file_model.id)

        account_ids = cls._get_account_ids_for_payment(batch_type)

        batch_header: str = cls.get_batch_header(batch_number, batch_type)

        current_app.logger.info("Processing accounts.")
        for account_id in account_ids:
            account_jv: str = ""
            pay_account: PaymentAccountModel = PaymentAccountModel.find_by_id(account_id)
            if not pay_account.billable:
                continue

            effective_date: str = cls.get_effective_date()
            ejv_header_model: EjvFileModel = EjvHeaderModel(
                payment_account_id=account_id,
                disbursement_status_code=DisbursementStatus.UPLOADED.value,
                ejv_file_id=ejv_file_model.id,
            ).flush()
            journal_name: str = cls.get_journal_name(ejv_header_model.id)

            transactions = cls._get_ejv_account_transactions(account_id)
            if not transactions:
                continue

            line_number: int = 0
            total: float = 0
            current_app.logger.info(f"Processing invoices and partial refunds for account_id: {account_id}.")
            for transaction in transactions:
                total += transaction.line_item.amount
                line_number += 1
                control_total += 1

                # If it's normal payment then the Line distribution goes as Credit,
                # else it goes as Debit as we need to debit the fund from BC registry GL.
                account_jv = account_jv + cls.get_jv_line(
                    batch_type,
                    cls.get_distribution_string(transaction.line_distribution),
                    transaction.line_item.description,
                    effective_date,
                    transaction.line_item.flow_through,
                    journal_name,
                    transaction.line_item.amount,
                    line_number,
                    "C" if not transaction.line_item.is_reversal else "D",
                )

                # If it's normal payment then the Gov account GL goes as Debit,
                # else it goes as Credit as we need to credit the fund back to ministry.
                line_number += 1
                control_total += 1
                account_jv = account_jv + cls.get_jv_line(
                    batch_type,
                    cls.get_distribution_string(transaction.gov_account_distribution),
                    transaction.line_item.description,
                    effective_date,
                    transaction.line_item.flow_through,
                    journal_name,
                    transaction.line_item.amount,
                    line_number,
                    "D" if not transaction.line_item.is_reversal else "C",
                )

            batch_total += total

            if total > 0:
                # A JV header for each account.
                control_total += 1
                account_jv = (
                    cls.get_jv_header(
                        batch_type,
                        cls.get_journal_batch_name(batch_number),
                        journal_name,
                        total,
                    )
                    + account_jv
                )
                ejv_content = ejv_content + account_jv

            current_app.logger.info("Creating ejv invoice link records and setting invoice status.")
            sequence = 1
            for transaction in transactions:
                sequence = cls._create_ejv_link_record(transaction, ejv_header_model, sequence)

                if transaction.line_item.target_type == EJVLinkType.INVOICE.value:
                    # If it's reversal, If there is no COMPLETED invoice reference, then no need to reverse it.
                    # Else mark it as CANCELLED, as new invoice reference will be created
                    if transaction.line_item.is_reversal:
                        if (
                            inv_ref := InvoiceReferenceModel.find_by_invoice_id_and_status(
                                transaction.target.id, InvoiceReferenceStatus.COMPLETED.value
                            )
                        ) is None:
                            continue
                        inv_ref.status_code = InvoiceReferenceStatus.CANCELLED.value
                    # This is to avoid duplicate invoice references.
                    # might already be created by another transaction(when invoice has service fees)
                    existing_ref = InvoiceReferenceModel.find_by_invoice_id_and_status(
                        transaction.target.id, InvoiceReferenceStatus.ACTIVE.value
                    )
                    if not existing_ref:
                        current_app.logger.debug(f"Creating Invoice Reference for invoice id: {transaction.target.id}")
                        inv_ref = InvoiceReferenceModel(
                            invoice_id=transaction.target.id,
                            invoice_number=generate_transaction_number(transaction.target.id),
                            reference_number=None,
                            status_code=InvoiceReferenceStatus.ACTIVE.value,
                        )
                        db.session.add(inv_ref)
                elif transaction.line_item.target_type == EJVLinkType.PARTIAL_REFUND.value:
                    partial_refund = RefundsPartialModel.find_by_id(transaction.target.id)
                    partial_refund.status = RefundsPartialStatus.REFUND_PROCESSING.value
                    db.session.add(partial_refund)

            db.session.flush()  # Instead of flushing every entity, flush all at once.

        if not ejv_content:
            db.session.rollback()
            return

        batch_trailer: str = cls.get_batch_trailer(batch_number, batch_total, batch_type, control_total)
        ejv_content = f"{batch_header}{ejv_content}{batch_trailer}"
        file_path_with_name, trg_file_path, _ = cls.create_inbox_and_trg_files(ejv_content, file_name)
        current_app.logger.info("Uploading to sftp.")
        cls.upload(ejv_content, file_name, file_path_with_name, trg_file_path)
        db.session.commit()

        # Sleep to prevent collision on file name.
        time.sleep(1)

    @classmethod
    def _create_ejv_link_record(cls, transaction, ejv_header_model, sequence):
        """Create EJV link record if it doesn't already exist."""
        # Possible this could already be created, eg two PLI.
        existing_ejv_link = (
            db.session.query(EjvLinkModel)
            .filter(
                EjvLinkModel.link_id == transaction.target.id,
                EjvLinkModel.link_type == transaction.line_item.target_type,
                EjvLinkModel.ejv_header_id == ejv_header_model.id,
            )
            .first()
        )

        if not existing_ejv_link:
            ejv_link = EjvLinkModel(
                link_id=transaction.target.id,
                link_type=transaction.line_item.target_type,
                ejv_header_id=ejv_header_model.id,
                disbursement_status_code=DisbursementStatus.UPLOADED.value,
                sequence=sequence,
            )
            db.session.add(ejv_link)
            sequence += 1

        return sequence

    @classmethod
    def _get_account_ids_for_payment(cls, batch_type) -> List[int]:
        """Return account IDs for payment."""
        # CREDIT : Distribution code against fee schedule
        # DEBIT : Distribution code against account.
        # Rule for GA. Credit is 112 and debit is 112. For BCREG client code is 112
        # Rule for GI. Credit is 112 and debit is not 112. For BCREG client code is 112
        bc_reg_client_code = current_app.config.get("CGI_BCREG_CLIENT_CODE")
        account_ids = (
            db.session.query(DistributionCodeModel.account_id)
            .filter(DistributionCodeModel.stop_ejv.is_(False) | DistributionCodeModel.stop_ejv.is_(None))
            .filter(DistributionCodeModel.account_id.isnot(None))
            .filter_boolean(batch_type == "GA", DistributionCodeModel.client == bc_reg_client_code)
            .filter_boolean(batch_type != "GA", DistributionCodeModel.client != bc_reg_client_code)
            .all()
        )
        return [account_id_tuple[0] for account_id_tuple in account_ids]

    @classmethod
    def _get_invoices_for_payment(cls, account_id: int) -> List[InvoiceModel]:
        """Return invoices for payments."""
        valid_statuses = (
            InvoiceStatus.APPROVED.value,
            InvoiceStatus.REFUND_REQUESTED.value,
        )
        invoice_ref_subquery = db.session.query(InvoiceReferenceModel.invoice_id).filter(
            InvoiceReferenceModel.status_code.in_((InvoiceReferenceStatus.ACTIVE.value,))
        )

        invoices: List[InvoiceModel] = (
            db.session.query(InvoiceModel)
            .filter(InvoiceModel.invoice_status_code.in_(valid_statuses))
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EJV.value)
            .filter(InvoiceModel.payment_account_id == account_id)
            .filter(InvoiceModel.id.notin_(invoice_ref_subquery))
            .all()
        )
        return invoices

    @classmethod
    def get_partial_refunds_invoices(cls, account_id: int) -> List[InvoiceModel]:
        """Get credit card partial refunds."""
        invoices: List[InvoiceModel] = (
            InvoiceModel.query.join(RefundsPartialModel, RefundsPartialModel.invoice_id == InvoiceModel.id)
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EJV.value)
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value)
            .filter(RefundsPartialModel.status == RefundsPartialStatus.REFUND_REQUESTED.value)
            .filter(InvoiceModel.payment_account_id == account_id)
            .order_by(InvoiceModel.id, RefundsPartialModel.id)
            .distinct(InvoiceModel.id)
            .all()
        )
        return invoices

    @classmethod
    def _get_ejv_account_transactions(cls, account_id: int) -> List[EjvTransaction]:
        """Return unified payment transactions for both invoices and partial refunds."""
        transactions = []
        invoices = cls._get_invoices_for_payment(account_id)
        partial_refund_invoices = cls.get_partial_refunds_invoices(account_id)
        if not invoices and not partial_refund_invoices:
            return []

        # Debit from GOV account GL
        debit_distribution_code = DistributionCodeModel.find_by_active_for_account(account_id)

        current_app.logger.info(f"Processing invoices for account_id: {account_id}.")

        payment_desc = f"{PaymentAccountModel.find_by_id(account_id).name[:100]:<100}"
        # Find all invoices for the gov account to pay.
        for inv in invoices:
            # If it's a JV reversal credit and debit is reversed.
            is_jv_reversal = inv.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value

            description = payment_desc[: -len(f"#{inv.id}")] + f"#{inv.id}"
            description = f"{description[:100]:<100}"

            for line in inv.payment_line_items:
                # Line can have 2 distribution, 1 for the total and another one for service fees.
                line_distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_id(
                    line.fee_distribution_id
                )
                if line.total > 0:
                    transactions.append(
                        EjvTransaction(
                            gov_account_distribution=debit_distribution_code,
                            line_distribution=line_distribution_code,
                            line_item=TransactionLineItem(
                                amount=line.total,
                                flow_through=f"{inv.id:<110}",
                                description=description,
                                is_reversal=is_jv_reversal,
                                target_type=EJVLinkType.INVOICE.value,
                            ),
                            target=inv,
                        )
                    )
                if line.service_fees > 0:
                    service_fee_distribution_code = DistributionCodeModel.find_by_id(
                        line_distribution_code.service_fee_distribution_code_id
                    )
                    transactions.append(
                        EjvTransaction(
                            gov_account_distribution=debit_distribution_code,
                            line_distribution=service_fee_distribution_code,
                            line_item=TransactionLineItem(
                                amount=line.service_fees,
                                flow_through=f"{inv.id:<110}",
                                description=description,
                                is_reversal=is_jv_reversal,
                                target_type=EJVLinkType.INVOICE.value,
                            ),
                            target=inv,
                        )
                    )
                if line.service_fees_gst > 0:
                    service_fee_gst_distribution_code = DistributionCodeModel.find_by_id(
                        line_distribution_code.service_fee_gst_distribution_code_id
                    )
                    transactions.append(
                        EjvTransaction(
                            gov_account_distribution=debit_distribution_code,
                            line_distribution=service_fee_gst_distribution_code,
                            line_item=TransactionLineItem(
                                amount=line.service_fees_gst,
                                flow_through=f"{inv.id:<110}",
                                description=description,
                                is_reversal=is_jv_reversal,
                                target_type=EJVLinkType.INVOICE.value,
                            ),
                            target=inv,
                        )
                    )
                if line.statutory_fees_gst > 0:
                    statutory_fees_gst_distribution_code = DistributionCodeModel.find_by_id(
                        line_distribution_code.statutory_fees_gst_distribution_code_id
                    )
                    transactions.append(
                        EjvTransaction(
                            gov_account_distribution=debit_distribution_code,
                            line_distribution=statutory_fees_gst_distribution_code,
                            line_item=TransactionLineItem(
                                amount=line.statutory_fees_gst,
                                flow_through=f"{inv.id:<110}",
                                description=description,
                                is_reversal=is_jv_reversal,
                                target_type=EJVLinkType.INVOICE.value,
                            ),
                            target=inv,
                        )
                    )

        # Process partial refunds
        current_app.logger.info(f"Processing partial refunds for account_id: {account_id}.")
        for pr_invoice in partial_refund_invoices:
            # Create description that combines account name and invoice number for partial refund
            description = payment_desc[: -len(f"#{pr_invoice.id}")] + f"#{pr_invoice.id}"
            description = f"{description[:100]:<100}"

            for pr in RefundsPartialModel.get_partial_refunds_for_invoice(pr_invoice.id):
                line = PaymentLineItemModel.find_by_id(pr.payment_line_item_id)
                line_distribution_code = DistributionCodeModel.find_by_id(line.fee_distribution_id)

                # For service fee refunds, use service fee distribution
                if pr.refund_type == RefundsPartialType.SERVICE_FEES.value:
                    line_distribution_code = DistributionCodeModel.find_by_id(
                        line_distribution_code.service_fee_distribution_code_id
                    )

                transactions.append(
                    EjvTransaction(
                        gov_account_distribution=debit_distribution_code,
                        line_distribution=line_distribution_code,
                        line_item=TransactionLineItem(
                            amount=pr.refund_amount,
                            flow_through=f"{f'{pr_invoice.id}-PR-{pr.id}':<110}",
                            description=description,
                            is_reversal=True,  # Partial refunds are always reversals
                            target_type=EJVLinkType.PARTIAL_REFUND.value,
                        ),
                        target=pr,
                    )
                )
        return transactions
