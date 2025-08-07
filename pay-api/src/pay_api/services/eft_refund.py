"""Module for EFT refunds that go tghrough the AP module via EFT."""

from decimal import Decimal
from typing import List

from flask import abort, current_app

from pay_api.dtos.eft_shortname import (
    EFTShortNameRefundGetRequest,
    EFTShortNameRefundPatchRequest,
    EFTShortNameRefundPostRequest,
)
from pay_api.exceptions import BusinessException, Error
from pay_api.models import EFTRefund as EFTRefundModel
from pay_api.models import EFTShortnames as EFTShortnamesModel
from pay_api.models import EFTShortnamesHistorical as EFTHistoryModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount
from pay_api.models.eft_credit import EFTCredit as EFTCreditModel
from pay_api.models.eft_credit_invoice_link import EFTCreditInvoiceLink as EFTCreditInvoiceLinkModel
from pay_api.services.auth import get_emails_with_keycloak_role
from pay_api.services.eft_short_name_historical import EFTShortnameHistorical as EFTHistoryService
from pay_api.services.email_service import ShortNameRefundEmailContent, send_email
from pay_api.utils.enums import (
    EFTCreditInvoiceStatus,
    EFTHistoricalTypes,
    EFTShortnameRefundStatus,
    InvoiceStatus,
    Role,
)
from pay_api.utils.user_context import UserContext, user_context


class EFTRefund:
    """Service to manage EFT Refunds."""

    @staticmethod
    @user_context
    def create_shortname_refund(refund: EFTShortNameRefundPostRequest, **kwargs):
        """Create refund. This method isn't for invoices, it's for shortname only."""
        refund.validate_for_refund_method()
        current_app.logger.debug(f"Starting shortname refund : {refund.short_name_id}")
        short_name = EFTShortnamesModel.find_by_id(refund.short_name_id)
        refund = EFTRefund._create_refund_model(refund)
        EFTRefund.refund_eft_credits(refund.short_name_id, refund.refund_amount)

        history = EFTHistoryService.create_shortname_refund(
            EFTHistoryModel(
                short_name_id=refund.short_name_id,
                amount=refund.refund_amount,
                credit_balance=EFTCreditModel.get_eft_credit_balance(refund.short_name_id),
                eft_refund_id=refund.id,
                is_processing=False,
                hidden=False,
            )
        ).flush()

        qualified_receiver_recipients = get_emails_with_keycloak_role(Role.EFT_REFUND.value)
        subject = f"Pending Refund Request for Short Name {short_name.short_name}"
        html_body = ShortNameRefundEmailContent(
            comment=refund.comment,
            decline_reason=refund.decline_reason,
            refund_amount=refund.refund_amount,
            refund_method=refund.refund_method,
            short_name_id=refund.short_name_id,
            short_name=short_name.short_name,
            status=EFTShortnameRefundStatus.PENDING_APPROVAL.value,
            url=f"{current_app.config.get('PAY_WEB_URL')}/eft/shortname-details/{refund.short_name_id}",
        ).render_body()
        send_email(qualified_receiver_recipients, subject, html_body)
        history.save()
        refund.save()

        return refund.to_dict()

    @staticmethod
    def get_shortname_refunds(data: EFTShortNameRefundGetRequest):
        """Get all refunds."""
        refunds = EFTRefundModel.find_refunds(data.statuses, data.short_name_id)
        return [refund.to_dict() for refund in refunds]

    @staticmethod
    def find_refund_by_id(refund_id: int) -> EFTRefundModel:
        """Find refund by id."""
        return EFTRefundModel.find_by_id(refund_id)

    @staticmethod
    def handle_invoice_refund(
        invoice: InvoiceModel,
        payment_account: PaymentAccount,
        cils: List[EFTCreditInvoiceLinkModel],
        is_partial_refund: bool = False,
    ) -> InvoiceStatus:
        """Create EFT Short name funds received historical record."""
        # 2. No EFT Credit Link - Job needs to reverse invoice in CFS
        # (Invoice needs to be reversed, receipt doesn't exist.)
        if not cils and not is_partial_refund:
            return InvoiceStatus.REFUND_REQUESTED.value

        if not cils and is_partial_refund:
            raise BusinessException(Error.EFT_PARTIAL_REFUND_MISSING_LINKS)

        latest_link = cils[0]
        sibling_cils = [cil for cil in cils if cil.link_group_id == latest_link.link_group_id]
        latest_eft_credit = EFTCreditModel.find_by_id(latest_link.eft_credit_id)
        link_group_id = EFTCreditInvoiceLinkModel.get_next_group_link_seq()
        existing_balance = EFTCreditModel.get_eft_credit_balance(latest_eft_credit.short_name_id)

        match latest_link.status_code:
            case EFTCreditInvoiceStatus.PENDING.value:
                # 3. EFT Credit Link - PENDING, CANCEL that link - restore balance to EFT credit existing call
                # (Invoice needs to be reversed, receipt doesn't exist.)
                for cil in sibling_cils:
                    EFTRefund.return_eft_credit(
                        eft_credit_link=cil,
                        refund_amount=cil.amount,
                        update_status=EFTCreditInvoiceStatus.CANCELLED.value,
                    )
                    cil.link_group_id = link_group_id
                    cil.flush()
            case EFTCreditInvoiceStatus.COMPLETED.value:
                # 4. EFT Credit Link - COMPLETED
                # (Full refund - Invoice needs to be reversed and receipt needs to be reversed.)
                # (Partial refund - Credit memo need to be created.)
                remaining_refund_amount = invoice.refund
                for cil in sibling_cils:
                    refund_amount = cil.amount if remaining_refund_amount >= cil.amount else remaining_refund_amount
                    EFTRefund.return_eft_credit(eft_credit_link=cil, refund_amount=refund_amount)
                    link_status = (
                        EFTCreditInvoiceStatus.REFUNDED.value
                        if is_partial_refund
                        else EFTCreditInvoiceStatus.PENDING_REFUND.value
                    )
                    EFTCreditInvoiceLinkModel(
                        eft_credit_id=cil.eft_credit_id,
                        status_code=link_status,
                        amount=refund_amount,
                        receipt_number=cil.receipt_number,
                        invoice_id=invoice.id,
                        link_group_id=link_group_id,
                    ).flush()

        current_balance = EFTCreditModel.get_eft_credit_balance(latest_eft_credit.short_name_id)
        if existing_balance != current_balance:
            short_name_history = EFTHistoryModel.find_by_related_group_link_id(latest_link.link_group_id)

            EFTHistoryService.create_invoice_refund(
                EFTHistoryModel(
                    short_name_id=latest_eft_credit.short_name_id,
                    amount=invoice.refund if is_partial_refund else invoice.total,
                    credit_balance=current_balance,
                    payment_account_id=payment_account.id,
                    related_group_link_id=link_group_id,
                    statement_number=(short_name_history.statement_number if short_name_history else None),
                    invoice_id=invoice.id,
                    is_processing=True,
                    hidden=False,
                ),
                is_partial_refund,
            ).flush()
        return InvoiceStatus.REFUND_REQUESTED.value

    @staticmethod
    def reverse_eft_credits(shortname_id: int, amount: Decimal):
        """Reverse the amount to eft_credits table based on short_name_id."""
        eft_credits = EFTCreditModel.get_eft_credits(shortname_id, include_zero_remaining=True)
        for credit in eft_credits:
            if credit.remaining_amount == credit.amount:
                continue
            if credit.remaining_amount > credit.amount:
                raise BusinessException(Error.EFT_CREDIT_AMOUNT_UNEXPECTED)

            credit_adjustment = min(amount, credit.amount - credit.remaining_amount)
            amount -= credit_adjustment
            credit.remaining_amount += credit_adjustment
            credit.flush()

        # Scenario where we tried to reverse an amount all the credits,
        # but for some reason our refund was more than the original amount on the credits.
        if amount > 0:
            raise BusinessException(Error.INVALID_REFUND)

    @staticmethod
    def refund_eft_credits(shortname_id: int, amount: Decimal):
        """Refund the amount to eft_credits table based on short_name_id."""
        eft_credits = EFTCreditModel.get_eft_credits(shortname_id)
        eft_credit_balance = EFTCreditModel.get_eft_credit_balance(shortname_id)
        if amount > eft_credit_balance or amount <= 0:
            raise BusinessException(Error.INVALID_REFUND)

        for credit in eft_credits:
            credit_amount = Decimal(credit.remaining_amount)
            if credit_amount <= 0:
                continue

            deduction = min(amount, credit_amount)
            credit.remaining_amount -= deduction
            amount -= deduction

            credit.flush()
        # Scenario where we couldn't subtract the remaining amount from the credits.
        if amount > 0:
            raise BusinessException(Error.INVALID_REFUND)

    @staticmethod
    @user_context
    def _approve_or_decline_refund(refund: EFTRefundModel, data: EFTShortNameRefundPatchRequest, **kwargs):
        """Approve or decline an EFT Refund."""
        user: UserContext = kwargs["user"]
        if not user.has_role(Role.EFT_REFUND_APPROVER.value):
            abort(403)
        if refund.status != EFTShortnameRefundStatus.PENDING_APPROVAL.value:
            raise BusinessException(Error.REFUND_ALREADY_FINALIZED)

        refund.comment = data.comment or refund.comment
        refund.status = data.status or refund.status
        refund.decision_by = user.user_name

        short_name = EFTShortnamesModel.find_by_id(refund.short_name_id)
        match data.status:
            case EFTShortnameRefundStatus.DECLINED.value:
                refund.decline_reason = data.decline_reason or refund.decline_reason
                EFTRefund.reverse_eft_credits(refund.short_name_id, refund.refund_amount)
                history = EFTHistoryModel.find_by_eft_refund_id(refund.id)[0]
                history.transaction_type = EFTHistoricalTypes.SN_REFUND_DECLINED.value
                history.credit_balance = EFTCreditModel.get_eft_credit_balance(refund.short_name_id)
                history.save()
                subject = f"Declined Refund Request for Short Name {short_name.short_name}"
                body = ShortNameRefundEmailContent(
                    comment=refund.comment,
                    decline_reason=refund.decline_reason,
                    refund_amount=refund.refund_amount,
                    refund_method=refund.refund_method,
                    short_name_id=refund.short_name_id,
                    short_name=short_name.short_name,
                    status=data.status,
                    url=f"{current_app.config.get('PAY_WEB_URL')}/eft/shortname-details/{refund.short_name_id}",
                ).render_body()
                expense_authority_recipients = get_emails_with_keycloak_role(Role.EFT_REFUND_APPROVER.value)
                send_email(expense_authority_recipients, subject, body)
            case EFTShortnameRefundStatus.APPROVED.value:
                if user.user_name == refund.created_by:
                    raise BusinessException(Error.EFT_REFUND_SAME_USER_APPROVAL_FORBIDDEN)
                history = EFTHistoryModel.find_by_eft_refund_id(refund.id)[0]
                history.transaction_type = EFTHistoricalTypes.SN_REFUND_APPROVED.value
                history.save()
                subject = f"Approved Refund Request for Short Name {short_name.short_name}"
                content = ShortNameRefundEmailContent(
                    comment=refund.comment,
                    decline_reason=refund.decline_reason,
                    refund_amount=refund.refund_amount,
                    refund_method=refund.refund_method,
                    short_name_id=refund.short_name_id,
                    short_name=short_name.short_name,
                    status=data.status,
                    url=f"{current_app.config.get('PAY_WEB_URL')}/eft/shortname-details/{refund.short_name_id}",
                )
                staff_body = content.render_body()
                expense_authority_recipients = get_emails_with_keycloak_role(Role.EFT_REFUND_APPROVER.value)
                send_email(expense_authority_recipients, subject, staff_body)
                client_recipients = [refund.refund_email]
                client_body = content.render_body(is_for_client=True)
                send_email(client_recipients, subject, client_body)
            case _:
                raise NotImplementedError("Invalid status")

    @staticmethod
    def _update_refund_cheque_status(refund: EFTRefundModel, data: EFTShortNameRefundPatchRequest):
        """Update EFT Refund cheque status."""
        if refund.status != EFTShortnameRefundStatus.APPROVED.value and data.cheque_status:
            raise BusinessException(Error.EFT_REFUND_CHEQUE_STATUS_INVALID_ACTION)
        refund.cheque_status = data.cheque_status or refund.cheque_status

    @staticmethod
    def update_shortname_refund(refund_id: int, data: EFTShortNameRefundPatchRequest) -> EFTRefundModel:
        """Update the refund status."""
        refund = EFTRefundModel.find_by_id(refund_id)
        if data.cheque_status:
            EFTRefund._update_refund_cheque_status(refund, data)
        else:
            EFTRefund._approve_or_decline_refund(refund, data)

        refund.save()
        return refund.to_dict()

    @staticmethod
    def _create_refund_model(refund: EFTShortNameRefundPostRequest) -> EFTRefundModel:
        """Create and return the EFTRefundModel instance."""
        # AP refund job should pick up this row and send back the amount in the refund via cheque.
        # For example if we had $500 on the EFT Shortname credits and we want to refund $300,
        # then the AP refund job should send a cheque for $300 to the supplier while leaving $200 on the credits.
        refund = EFTRefundModel(
            short_name_id=refund.short_name_id,
            refund_amount=refund.refund_amount,
            cas_supplier_number=refund.cas_supplier_number,
            cas_supplier_site=refund.cas_supplier_site,
            refund_email=refund.refund_email,
            refund_method=refund.refund_method,
            comment=refund.comment,
            status=EFTShortnameRefundStatus.PENDING_APPROVAL.value,
            entity_name=refund.entity_name,
            street=refund.street,
            street_additional=refund.street_additional,
            city=refund.city,
            region=refund.region,
            postal_code=refund.postal_code,
            country=refund.country,
            delivery_instructions=refund.delivery_instructions,
        )
        refund.flush()
        return refund

    @staticmethod
    def return_eft_credit(
        eft_credit_link: EFTCreditInvoiceLinkModel, refund_amount: Decimal, update_status: str = None
    ) -> EFTCreditModel:
        """Return EFT Credit Invoice Link amount to EFT Credit."""
        eft_credit = EFTCreditModel.find_by_id(eft_credit_link.eft_credit_id)
        eft_credit.remaining_amount += refund_amount

        if eft_credit.remaining_amount > eft_credit.amount:
            raise BusinessException(Error.EFT_CREDIT_AMOUNT_UNEXPECTED)

        if update_status:
            eft_credit_link.status_code = update_status

        return eft_credit
