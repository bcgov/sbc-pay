"""Partner Disbursements service."""

from datetime import datetime, timezone

from flask import current_app

from pay_api.models.corp_type import CorpType as CorpTypeModel
from pay_api.models.invoice import Invoice as InvoiceModel
from pay_api.models.partner_disbursements import PartnerDisbursements as PartnerDisbursementsModel
from pay_api.models.refunds_partial import RefundsPartial as RefundsPartialModel
from pay_api.utils.enums import DisbursementStatus, EJVLinkType, PaymentMethod


class PartnerDisbursements:
    """Partner Disbursements service."""

    @staticmethod
    def _skip_partner_disbursement(invoice: InvoiceModel) -> bool:
        """Determine if partner disbursement should be skipped."""
        return (
            invoice.total - invoice.service_fees <= 0
            or bool(CorpTypeModel.find_by_code(invoice.corp_type_code).has_partner_disbursements) is False
        )

    @staticmethod
    def handle_payment(invoice: InvoiceModel):
        """Insert a partner disbursement row if necessary with is_reversal as False."""
        if PartnerDisbursements._skip_partner_disbursement(invoice):
            return

        latest_active_disbursement = PartnerDisbursementsModel.find_by_target_latest_exclude_cancelled(
            invoice.id, EJVLinkType.INVOICE.value
        )

        if latest_active_disbursement is None or latest_active_disbursement.is_reversal:
            PartnerDisbursementsModel(
                amount=invoice.total - invoice.service_fees,
                is_reversal=False,
                partner_code=invoice.corp_type_code,
                status_code=DisbursementStatus.WAITING_FOR_JOB.value,
                target_id=invoice.id,
                target_type=EJVLinkType.INVOICE.value,
            ).flush()
        else:
            # If this was already called at invoice creation, it might be called again when mapping credits.
            # If we're mapping credits after invoice creation, we don't want to create a new row.
            current_app.logger.info(f"Skipping Partner Disbursement Payment creation for {invoice.id} already exists.")

    @staticmethod
    def handle_reversal(invoice: InvoiceModel):
        """Cancel existing row or insert new row if non reversal is found."""
        if PartnerDisbursements._skip_partner_disbursement(invoice):
            return

        if not (
            latest_active_disbursement := PartnerDisbursementsModel.find_by_target_latest_exclude_cancelled(
                invoice.id, EJVLinkType.INVOICE.value
            )
        ):
            current_app.logger.error(f"Existing Partner Disbursement not found for invoice {invoice.id}")
            return

        if latest_active_disbursement.is_reversal is True:
            current_app.logger.error(f"Duplicate Existing Partner Disbursement Reversal for invoice {invoice.id}")
            return

        match latest_active_disbursement.status_code:
            case DisbursementStatus.WAITING_FOR_JOB.value:
                # Note we never CANCEL a reversal.
                latest_active_disbursement.status_code = DisbursementStatus.CANCELLED.value
                latest_active_disbursement.processed_on = datetime.now(tz=timezone.utc)
                latest_active_disbursement.flush()
            case _:
                # We'll assume errored status should be fixed in the future to COMPLETED hopefully.
                PartnerDisbursementsModel(
                    amount=invoice.total - invoice.service_fees,
                    is_reversal=True,
                    partner_code=invoice.corp_type_code,
                    status_code=DisbursementStatus.WAITING_FOR_JOB.value,
                    target_id=invoice.id,
                    target_type=EJVLinkType.INVOICE.value,
                ).flush()

    @staticmethod
    def handle_partial_refund(partial_refund: RefundsPartialModel, invoice: InvoiceModel):
        """Insert a partner disbursement row if necessary with is_reversal as False."""
        if PartnerDisbursements._skip_partner_disbursement(invoice):
            return

        # Internal invoices aren't disbursed to partners, DRAWDOWN is handled by the mainframe.
        if invoice.payment_method_code in [PaymentMethod.INTERNAL.value, PaymentMethod.DRAWDOWN.value]:
            return

        latest_active_disbursement = PartnerDisbursementsModel.find_by_target_latest_exclude_cancelled(
            partial_refund.id, EJVLinkType.PARTIAL_REFUND.value
        )

        if latest_active_disbursement is None:
            PartnerDisbursementsModel(
                amount=partial_refund.refund_amount,
                is_reversal=True,
                partner_code=invoice.corp_type_code,
                status_code=DisbursementStatus.WAITING_FOR_JOB.value,
                target_id=partial_refund.id,
                target_type=EJVLinkType.PARTIAL_REFUND.value,
            ).flush()
        else:
            current_app.logger.info(
                f"Skipping Partner Disbursement Partial Refund creation for {partial_refund.id} already exists."
            )
