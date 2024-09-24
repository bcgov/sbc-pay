"""Module for EFT refunds that go tghrough the AP module via EFT."""
from decimal import Decimal
from typing import List
from flask import current_app
from pay_api.dtos.eft_shortname import EFTShortNameRefundGetRequest, EFTShortNameRefundPatchRequest
from pay_api.exceptions import BusinessException, Error
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import EFTRefund as EFTRefundModel
from pay_api.models import PaymentAccount
from pay_api.models.eft_refund_email_list import EFTRefundEmailList
from pay_api.models.eft_credit import EFTCredit as EFTCreditModel
from pay_api.models.eft_credit_invoice_link import EFTCreditInvoiceLink as EFTCreditInvoiceLinkModel
from pay_api.models import EFTShortnamesHistorical as EFTHistoryModel
from pay_api.models import EFTShortnames as EFTShortnamesModel
from pay_api.services.email_service import ShortNameRefundEmailContent, send_email
from pay_api.services.eft_short_name_historical import EFTShortnameHistorical as EFTHistoryService
from pay_api.utils.enums import EFTCreditInvoiceStatus, EFTShortnameRefundStatus, InvoiceStatus
from pay_api.utils.user_context import user_context
from pay_api.utils.util import get_str_by_path


class EFTRefund:
    """Service to manage EFT Refunds."""

    @staticmethod
    @user_context
    def create_shortname_refund(request: dict, **kwargs):
        """Create refund."""
        # This method isn't for invoices, it's for shortname only.
        shortname_id = int(get_str_by_path(request, 'shortNameId'))
        amount = Decimal(get_str_by_path(request, 'refundAmount'))
        comment = get_str_by_path(request, 'comment')

        if amount <= 0:
            raise BusinessException(Error.INVALID_REFUND)

        current_app.logger.debug(f'Starting shortname refund : {shortname_id}')

        shortname = EFTShortnamesModel.find_by_id(shortname_id)
        refund = EFTRefund._create_refund_model(request, shortname_id, amount, comment)
        EFTRefund.refund_eft_credits(shortname_id, amount)

        history = EFTHistoryService.create_shortname_refund(
            EFTHistoryModel(short_name_id=shortname_id,
                            amount=amount,
                            credit_balance=EFTCreditModel.get_eft_credit_balance(shortname_id),
                            eft_refund_id=refund.id,
                            is_processing=False,
                            hidden=False)).flush()

        recipients = EFTRefundEmailList.find_all_emails()
        subject = f'Pending Refund Request for Short Name {shortname.short_name}'
        html_body = ShortNameRefundEmailContent(
            comment=comment,
            decline_reason=refund.decline_reason,
            refund_amount=amount,
            short_name_id=shortname_id,
            short_name=shortname.short_name,
            status=EFTShortnameRefundStatus.PENDING_APPROVAL.value,
            url=f"{current_app.config.get('AUTH_WEB_URL')}/pay/shortname-details/{shortname_id}",
        ).render_body()
        send_email(recipients, subject, html_body, **kwargs)
        history.save()
        refund.save()

        return refund.to_dict()

    @staticmethod
    def get_shortname_refunds(data: EFTShortNameRefundGetRequest):
        """Get all refunds."""
        refunds = EFTRefundModel.find_refunds(data.statuses)
        return [refund.to_dict() for refund in refunds]

    @staticmethod
    def find_refund_by_id(refund_id: int) -> EFTRefundModel:
        """Find refund by id."""
        return EFTRefundModel.find_by_id(refund_id)

    @staticmethod
    def handle_invoice_refund(invoice: InvoiceModel,
                              payment_account: PaymentAccount,
                              cils: List[EFTCreditInvoiceLinkModel]) -> InvoiceStatus:
        """Create EFT Short name funds received historical record."""
        # 2. No EFT Credit Link - Job needs to reverse invoice in CFS
        # (Invoice needs to be reversed, receipt doesn't exist.)
        if not cils:
            return InvoiceStatus.REFUND_REQUESTED.value

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
                    EFTRefund.return_eft_credit(cil, EFTCreditInvoiceStatus.CANCELLED.value)
                    cil.link_group_id = link_group_id
                    cil.flush()
            case EFTCreditInvoiceStatus.COMPLETED.value:
                # 4. EFT Credit Link - COMPLETED
                # (Invoice needs to be reversed and receipt needs to be reversed.)
                # reversal_total = Decimal('0')
                for cil in sibling_cils:
                    EFTRefund.return_eft_credit(cil)
                    EFTCreditInvoiceLinkModel(
                        eft_credit_id=cil.eft_credit_id,
                        status_code=EFTCreditInvoiceStatus.PENDING_REFUND.value,
                        amount=cil.amount,
                        receipt_number=cil.receipt_number,
                        invoice_id=invoice.id,
                        link_group_id=link_group_id).flush()
                    # if corp_type := CorpTypeModel.find_by_code(invoice.corp_type_code):
                    #     if corp_type.has_partner_disbursements:
                    #         reversal_total += cil.amount

                # if reversal_total > 0:
                #     PartnerDisbursementsModel(
                #         amount=reversal_total,
                #         is_reversal=True,
                #         partner_code=invoice.corp_type_code,
                #         status_code=DisbursementStatus.WAITING_FOR_JOB.value,
                #         target_id=invoice.id,
                #         target_type=EJVLinkType.INVOICE.value
                #     ).flush()

        current_balance = EFTCreditModel.get_eft_credit_balance(latest_eft_credit.short_name_id)
        if existing_balance != current_balance:
            short_name_history = EFTHistoryModel.find_by_related_group_link_id(latest_link.link_group_id)
            EFTHistoryService.create_invoice_refund(
                EFTHistoryModel(short_name_id=latest_eft_credit.short_name_id,
                                amount=invoice.total,
                                credit_balance=current_balance,
                                payment_account_id=payment_account.id,
                                related_group_link_id=link_group_id,
                                statement_number=short_name_history.statement_number if short_name_history else None,
                                invoice_id=invoice.id,
                                is_processing=True,
                                hidden=False)).flush()

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
    def update_shortname_refund(refund_id: int, data: EFTShortNameRefundPatchRequest, **kwargs) -> EFTRefundModel:
        """Update the refund status."""
        refund = EFTRefundModel.find_by_id(refund_id)
        if refund.status != EFTShortnameRefundStatus.PENDING_APPROVAL.value:
            raise BusinessException(Error.REFUND_ALREADY_FINALIZED)
        refund.comment = data.comment
        refund.status = data.status
        refund.decline_reason = data.decline_reason
        refund.save_or_add(auto_save=False)
        shortname = EFTShortnamesModel.find_by_id(refund.short_name_id)
        recipients = EFTRefundEmailList.find_all_emails()
        match data.status:
            case EFTShortnameRefundStatus.DECLINED.value:
                EFTRefund.reverse_eft_credits(refund.short_name_id, refund.refund_amount)
                EFTHistoryService.create_shortname_refund(
                    EFTHistoryModel(short_name_id=refund.short_name_id,
                                    amount=-refund.refund_amount,
                                    credit_balance=EFTCreditModel.get_eft_credit_balance(refund.short_name_id),
                                    eft_refund_id=refund.id,
                                    is_processing=False,
                                    hidden=False)).save()
                subject = f'Declined Refund Request for Short Name {shortname.short_name}'
                body = ShortNameRefundEmailContent(
                    comment=refund.comment,
                    decline_reason=refund.decline_reason,
                    refund_amount=refund.refund_amount,
                    short_name_id=refund.short_name_id,
                    short_name=shortname.short_name,
                    status=data.status,
                    url=f"{current_app.config.get('AUTH_WEB_URL')}/pay/shortname-details/{refund.short_name_id}",
                ).render_body()
                send_email(recipients, subject, body, **kwargs)
            case EFTShortnameRefundStatus.APPROVED.value:
                subject = f'Approved Refund Request for Short Name {shortname.short_name}'
                body = ShortNameRefundEmailContent(
                    comment=refund.comment,
                    decline_reason=refund.decline_reason,
                    refund_amount=refund.refund_amount,
                    short_name_id=refund.short_name_id,
                    short_name=shortname.short_name,
                    status=data.status,
                    url=f"{current_app.config.get('AUTH_WEB_URL')}/pay/shortname-details/{refund.short_name_id}",
                ).render_body()
                send_email(recipients, subject, body, **kwargs)
            case _:
                pass
        return refund.to_dict()

    @staticmethod
    def _create_refund_model(request: dict, shortname_id: int, amount: Decimal, comment: str) -> EFTRefundModel:
        """Create and return the EFTRefundModel instance."""
        # AP refund job should pick up this row and send back the amount in the refund via cheque.
        # For example if we had $500 on the EFT Shortname credits and we want to refund $300,
        # then the AP refund job should send a cheque for $300 to the supplier while leaving $200 on the credits.
        refund = EFTRefundModel(
            short_name_id=shortname_id,
            refund_amount=amount,
            cas_supplier_number=get_str_by_path(request, 'casSupplierNum'),
            refund_email=get_str_by_path(request, 'refundEmail'),
            comment=comment
        )
        refund.status = EFTCreditInvoiceStatus.PENDING_REFUND
        refund.flush()
        return refund

    @staticmethod
    def return_eft_credit(eft_credit_link: EFTCreditInvoiceLinkModel,
                          update_status: str = None) -> EFTCreditModel:
        """Return EFT Credit Invoice Link amount to EFT Credit."""
        eft_credit = EFTCreditModel.find_by_id(eft_credit_link.eft_credit_id)
        eft_credit.remaining_amount += eft_credit_link.amount

        if eft_credit.remaining_amount > eft_credit.amount:
            raise BusinessException(Error.EFT_CREDIT_AMOUNT_UNEXPECTED)

        if update_status:
            eft_credit_link.status_code = update_status

        return eft_credit
