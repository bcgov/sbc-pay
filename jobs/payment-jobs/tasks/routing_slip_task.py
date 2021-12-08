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
"""Task to for linking routing slips."""
from datetime import datetime
from typing import List

from flask import current_app
from pay_api import db
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.services.cfs_service import CFSService
from pay_api.utils.enums import (
    CfsAccountStatus, InvoiceReferenceStatus, InvoiceStatus, LineItemStatus, PaymentMethod, PaymentStatus,
    RoutingSlipStatus)
from sentry_sdk import capture_message


class RoutingSlipTask:  # pylint:disable=too-few-public-methods
    """Task to link routing slips."""

    @classmethod
    def link_routing_slips(cls):
        """Create invoice in CFS.

        Steps:
        1. Find all pending rs with pending status.
        1. Notify mailer
        """
        routing_slips = db.session.query(RoutingSlipModel) \
            .join(PaymentAccountModel, PaymentAccountModel.id == RoutingSlipModel.payment_account_id) \
            .join(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id) \
            .filter(RoutingSlipModel.status == RoutingSlipStatus.LINKED.value) \
            .filter(CfsAccountModel.status == CfsAccountStatus.ACTIVE.value).all()

        for routing_slip in routing_slips:

            # 1.reverse the child routing slip
            # 2.create receipt to the parent
            # 3.change the payment account of child to parent
            # 4. change the status

            try:
                current_app.logger.debug(f'Reverse receipt {routing_slip.number}')
                payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(
                    routing_slip.payment_account_id)
                cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(
                    payment_account.id)

                # reverse routing slip receipt
                CFSService.reverse_rs_receipt_in_cfs(cfs_account, routing_slip.number)
                cfs_account.status = CfsAccountStatus.INACTIVE.value

                # apply receipt to parent cfs account
                parent_rs: RoutingSlipModel = RoutingSlipModel.find_by_number(routing_slip.parent_number)
                parent_payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(
                    parent_rs.payment_account_id)

                parent_cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(
                    parent_payment_account.id)

                # For linked routing slip receipts, append 'L' to the number to avoid duplicate error
                receipt_number = f'{routing_slip.number}L'
                CFSService.create_cfs_receipt(cfs_account=parent_cfs_account,
                                              rcpt_number=receipt_number,
                                              rcpt_date=routing_slip.routing_slip_date.strftime('%Y-%m-%d'),
                                              amount=routing_slip.total,
                                              payment_method=parent_payment_account.payment_method)

                routing_slip.save()

            except Exception as e:  # NOQA # pylint: disable=broad-except
                capture_message(
                    f'Error on Linking Routing Slip number:={routing_slip.number}, '
                    f'routing slip : {routing_slip.id}, ERROR : {str(e)}', level='error')
                current_app.logger.error(e)
                continue

    @classmethod
    def process_nsf(cls):
        """Process NSF routing slips.

        Steps:
        1. Find all routing slips with NSF status.
        2. Reverse the receipt for the NSF routing slips.
        3. Add an invoice for NSF fees.
        """
        routing_slips: List[RoutingSlipModel] = db.session.query(RoutingSlipModel) \
            .join(PaymentAccountModel, PaymentAccountModel.id == RoutingSlipModel.payment_account_id) \
            .join(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id) \
            .filter(RoutingSlipModel.status == RoutingSlipStatus.NSF.value) \
            .filter(CfsAccountModel.status == CfsAccountStatus.ACTIVE.value).all()

        current_app.logger.info(f'Found {len(routing_slips)} to process NSF.')
        print('routing_slips-->', routing_slips)
        for routing_slip in routing_slips:
            # 1. Reverse the routing slip receipt.
            # 2. Reverse all the child receipts.
            # 3. Change the CFS Account status to FREEZE.
            try:
                current_app.logger.debug(f'Reverse receipt {routing_slip.number}')
                payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(routing_slip.payment_account_id)
                cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(payment_account.id)

                # Find all child routing slip and reverse it, as all linked routing slips are also considered as NSF.
                child_routing_slips: List[RoutingSlipModel] = RoutingSlipModel.find_children(routing_slip.number)
                for rs in (routing_slip, *child_routing_slips):
                    receipt_number = rs.number
                    if rs.parent_number:
                        receipt_number = f'{receipt_number}L'
                    CFSService.reverse_rs_receipt_in_cfs(cfs_account, receipt_number)

                    for payment in db.session.query(PaymentModel)\
                            .filter(PaymentModel.receipt_number == receipt_number).all():
                        payment.payment_status_code = PaymentStatus.FAILED.value

                # Update the CFS Account status to FREEZE.
                cfs_account.status = CfsAccountStatus.FREEZE.value

                # Update all invoice status to CREATED.
                invoices: List[InvoiceModel] = db.session.query(InvoiceModel)\
                    .filter(InvoiceModel.routing_slip == routing_slip.number) \
                    .filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value) \
                    .all()
                for inv in invoices:
                    # Reset the statuses
                    inv.invoice_status_code = InvoiceStatus.CREATED.value
                    inv_ref = InvoiceReferenceModel.find_reference_by_invoice_id_and_status(
                        inv.id, InvoiceReferenceStatus.COMPLETED.value
                    )
                    inv_ref.status_code = InvoiceReferenceStatus.CANCELLED.value
                    # Delete receipts as receipts are reversed in CFS.
                    for receipt in ReceiptModel.find_all_receipts_for_invoice(inv.id):
                        db.session.delete(receipt)

                inv = cls._create_nsf_invoice(cfs_account, routing_slip.number, payment_account)
                # Reduce the NSF fee from remaining amount.
                routing_slip.remaining_amount = float(routing_slip.remaining_amount) - inv.total
                routing_slip.save()

            except Exception as e:  # NOQA # pylint: disable=broad-except
                capture_message(
                    f'Error on Processing NSF for :={routing_slip.number}, '
                    f'routing slip : {routing_slip.id}, ERROR : {str(e)}', level='error')
                current_app.logger.error(e)
                continue

    @classmethod
    def _create_nsf_invoice(cls, cfs_account: CfsAccountModel, rs_number: str,
                            payment_account: PaymentAccountModel) -> InvoiceModel:
        """Create Invoice, line item and invoice reference records."""
        fee_schedule: FeeScheduleModel = FeeScheduleModel.find_by_filing_type_and_corp_type(corp_type_code='BCR',
                                                                                            filing_type_code='NSF')
        invoice = InvoiceModel(
            bcol_account=payment_account.bcol_account,
            payment_account_id=payment_account.id,
            cfs_account_id=cfs_account.id,
            invoice_status_code=InvoiceStatus.CREATED.value,
            total=fee_schedule.fee.amount,
            service_fees=0,
            paid=0,
            payment_method_code=PaymentMethod.INTERNAL.value,
            corp_type_code='BCR',
            created_on=datetime.now(),
            created_by='SYSTEM',
            routing_slip=rs_number
        )
        invoice = invoice.save()
        distribution: DistributionCodeModel = DistributionCodeModel.find_by_active_for_fee_schedule(
            fee_schedule.fee_schedule_id)

        line_item = PaymentLineItemModel(
            invoice_id=invoice.id,
            total=invoice.total,
            fee_schedule_id=fee_schedule.fee_schedule_id,
            description=fee_schedule.filing_type.description,
            filing_fees=invoice.total,
            gst=0,
            priority_fees=0,
            pst=0,
            future_effective_fees=0,
            line_item_status_code=LineItemStatus.ACTIVE.value,
            service_fees=0,
            fee_distribution_id=distribution.distribution_code_id)
        line_item.save()

        return invoice
