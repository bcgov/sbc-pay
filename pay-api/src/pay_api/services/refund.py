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
"""Service to manage Receipt."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Credit as CreditModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import Refund as RefundModel
from pay_api.services.cfs_service import CFSService
from pay_api.services.queue_publisher import publish_response
from pay_api.utils.constants import REFUND_SUCCESS_MESSAGES
from pay_api.utils.enums import (
    InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus, Role, RoutingSlipStatus)
from pay_api.utils.errors import Error
from pay_api.utils.user_context import UserContext, user_context
from pay_api.utils.util import get_local_formatted_date_time, get_str_by_path

from .fas.routing_slip import RoutingSlipModel


class RefundService:  # pylint: disable=too-many-instance-attributes
    """Service to hold and manage refund instance."""

    def __init__(self):
        """Return a refund object."""
        # Waiting Fix : https://github.com/PyCQA/pylint/issues/3882
        # pylint:disable=unsubscriptable-object
        self.__dao: Optional[RefundModel] = None
        self._id: Optional[int] = None
        self._invoice_id: Optional[int] = None
        self._routing_slip_id: Optional[int] = None
        self._requested_date: Optional[datetime] = None
        self._details: Optional[Dict] = None
        self._reason: Optional[str] = None
        self._requested_by: Optional[str] = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = RefundModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.invoice_id: int = self._dao.invoice_id
        self.routing_slip_id: int = self._dao.routing_slip_id
        self.requested_date: datetime = self._dao.requested_date
        self.reason: str = self._dao.reason
        self.requested_by: str = self._dao.requested_by
        self.details: Dict = self._dao.details

    @property
    def id(self) -> int:
        """Return the _id."""
        return self._id

    @id.setter
    def id(self, value: int):
        """Set the id."""
        self._id = value
        self._dao.id = value

    @property
    def invoice_id(self) -> int:
        """Return the _invoice_id."""
        return self._invoice_id

    @invoice_id.setter
    def invoice_id(self, value: int):
        """Set the invoice_id."""
        self._invoice_id = value
        self._dao.invoice_id = value

    @property
    def routing_slip_id(self) -> int:
        """Return the _routing_slip_id."""
        return self._routing_slip_id

    @routing_slip_id.setter
    def routing_slip_id(self, value: int):
        """Set the routing_slip_id."""
        self._routing_slip_id = value
        self._dao.routing_slip_id = value

    @property
    def requested_date(self) -> datetime:
        """Return the requested_date."""
        return self._requested_date

    @requested_date.setter
    def requested_date(self, value: datetime):
        """Set the filing_fees."""
        self._requested_date = value
        self._dao.requested_date = value

    @property
    def reason(self) -> Optional[str]:  # pylint:disable=unsubscriptable-object
        """Return the _reason."""
        return self._reason

    @reason.setter
    def reason(self, value: datetime):
        """Set the reason."""
        self._reason = value
        self._dao.reason = value

    @property
    def requested_by(self) -> Optional[str]:  # pylint:disable=unsubscriptable-object
        """Return the requested_by."""
        return self.requested_by

    @requested_by.setter
    def requested_by(self, value: str):
        """Set the reason."""
        self._requested_by = value
        self._dao.requested_by = value

    @property
    def details(self):
        """Return the details."""
        return self._details

    @details.setter
    def details(self, value: str):
        """Set the details."""
        self._details = value
        self._dao.details = value

    def save(self) -> RefundModel:
        """Save the information to the DB and commit."""
        return self._dao.save()

    def flush(self) -> RefundModel:
        """Save the information to the DB and flush."""
        return self._dao.flush()

    @classmethod
    @user_context
    def create_routing_slip_refund(cls, routing_slip_number: str, request: Dict[str, str], **kwargs) -> Dict[str, str]:
        """Create Routing slip refund."""
        current_app.logger.debug('<create Routing slip  refund')
        #
        # check if routing slip exists
        # validate user role -> update status of routing slip
        # check refunds table
        #   if Yes ; update the data [only with whatever is in payload]
        #   if not ; create new entry
        # call cfs
        rs_model = RoutingSlipModel.find_by_number(routing_slip_number)
        if not rs_model:
            raise BusinessException(Error.RS_DOESNT_EXIST)
        reason = get_str_by_path(request, 'reason')
        if (refund_status := get_str_by_path(request, 'status')) is None:
            raise BusinessException(Error.INVALID_REQUEST)
        user_name = kwargs['user'].user_name
        if rs_model.remaining_amount == 0:
            raise BusinessException(Error.INVALID_REQUEST)  # refund not possible for zero amount routing slips

        is_refund_finalized = refund_status in (RoutingSlipStatus.REFUND_AUTHORIZED.value,
                                                RoutingSlipStatus.REFUND_REJECTED.value)
        if is_refund_finalized:
            RefundService._is_authorised_refund()

        # Rejected refund makes routing slip active
        if refund_status == RoutingSlipStatus.REFUND_REJECTED.value:
            refund_status = RoutingSlipStatus.ACTIVE.value
            reason = f'Refund Rejected by {user_name}'

        rs_model.status = refund_status
        rs_model.flush()

        refund: RefundService = RefundService()
        refund_dao = RefundModel.find_by_routing_slip_id(rs_model.id)
        if refund_dao:
            refund._dao = refund_dao

        if not is_refund_finalized:
            # do not update these for approval/rejections

            refund.routing_slip_id = rs_model.id
            refund.requested_by = kwargs['user'].user_name
            refund.requested_date = datetime.now()

        refund.reason = reason
        if details := request.get('details'):
            refund.details = details

        refund.save()
        message = REFUND_SUCCESS_MESSAGES.get(f'ROUTINGSLIP.{rs_model.status}')
        return {'message': message}

    @staticmethod
    @user_context
    def _is_authorised_refund(**kwargs):
        user: UserContext = kwargs['user']
        has_refund_approver_role = Role.FAS_REFUND_APPROVER.value in user.roles
        if not has_refund_approver_role:
            raise BusinessException(Error.INVALID_REQUEST)

    @classmethod
    @user_context
    def create_refund(cls, invoice_id: int, request: Dict[str, str], **kwargs) -> Dict[str, str]:
        """Create refund."""
        current_app.logger.debug('<create refund')
        # Do validation by looking up the invoice
        invoice: InvoiceModel = InvoiceModel.find_by_id(invoice_id)

        paid_statuses = (
            InvoiceStatus.PAID.value, InvoiceStatus.APPROVED.value, InvoiceStatus.UPDATE_REVENUE_ACCOUNT.value
        )

        if invoice.invoice_status_code not in paid_statuses:
            raise BusinessException(Error.INVALID_REQUEST)

        refund: RefundService = RefundService()
        refund.invoice_id = invoice_id
        refund.reason = get_str_by_path(request, 'reason')
        refund.requested_by = kwargs['user'].user_name
        refund.requested_date = datetime.now()
        refund.flush()

        message = REFUND_SUCCESS_MESSAGES.get(f'{invoice.payment_method_code}.{invoice.invoice_status_code}')

        cls._process_cfs_refund(invoice)

        # set invoice status
        invoice.refund = invoice.total  # no partial refund
        invoice.save()
        return {'message': message}

    @classmethod
    def _process_cfs_refund(cls, invoice: InvoiceModel):
        """Process refund in CFS."""
        if invoice.payment_method_code in ([PaymentMethod.DIRECT_PAY.value, PaymentMethod.DRAWDOWN.value]):
            cls._publish_to_mailer(invoice)
            payment: PaymentModel = PaymentModel.find_payment_for_invoice(invoice.id)
            payment.payment_status_code = PaymentStatus.REFUNDED.value
            payment.flush()
            invoice.invoice_status_code = InvoiceStatus.REFUND_REQUESTED.value
        elif invoice.payment_method_code in (
                [PaymentMethod.ONLINE_BANKING.value, PaymentMethod.PAD.value, PaymentMethod.CC.value]):
            invoice.invoice_status_code = InvoiceStatus.REFUNDED.value
            # Create credit memo in CFS if the invoice status is PAID.
            # Don't do anything is the status is APPROVED.
            if invoice.invoice_status_code == InvoiceStatus.APPROVED.value \
                    and InvoiceReferenceModel. \
                    find_reference_by_invoice_id_and_status(invoice.id, InvoiceReferenceStatus.ACTIVE.value
                                                            ) is None:
                return

            cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(invoice.payment_account_id)
            line_items: List[PaymentLineItemModel] = []
            for line_item in invoice.payment_line_items:
                line_items.append(PaymentLineItemModel.find_by_id(line_item.id))

            cms_response = CFSService.create_cms(line_items=line_items, cfs_account=cfs_account)
            # TODO Create a payment record for this to show up on transactions, when the ticket comes.
            # Create a credit with CM identifier as CMs are not reported in payment interface file
            # until invoice is applied.
            CreditModel(cfs_identifier=cms_response.get('credit_memo_number'),
                        is_credit_memo=True,
                        amount=invoice.total,
                        remaining_amount=invoice.total,
                        account_id=invoice.payment_account_id).save()

            # Add up the credit amount and update payment account table.
            payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(invoice.payment_account_id)
            payment_account.credit = (payment_account.credit or 0) + invoice.total
            payment_account.save()

        elif invoice.payment_method_code == PaymentMethod.INTERNAL.value:
            # Allow if the payment is done using new FAS system.
            is_fas_payment = invoice.routing_slip and RoutingSlipModel.find_by_number(invoice.routing_slip)
            if not is_fas_payment:
                if invoice.total == 0:
                    raise BusinessException(Error.NO_FEE_REFUND)

                raise BusinessException(Error.ROUTING_SLIP_REFUND)
        elif invoice.payment_method_code == PaymentMethod.EJV.value:
            invoice.invoice_status_code = InvoiceStatus.REFUND_REQUESTED.value
        else:
            raise BusinessException(Error.INVALID_REQUEST)

    @classmethod
    def _publish_to_mailer(cls, invoice: InvoiceModel):
        """Construct message and send to mailer queue."""
        receipt: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice_id=invoice.id)
        invoice_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_reference_by_invoice_id_and_status(
            invoice_id=invoice.id, status_code=InvoiceReferenceStatus.COMPLETED.value)
        payment_transaction: PaymentTransactionModel = PaymentTransactionModel.find_recent_completed_by_invoice_id(
            invoice_id=invoice.id)
        message_type: str = f'bc.registry.payment.{invoice.payment_method_code.lower()}.refundRequest'
        filing_description = ''
        for line_item in invoice.payment_line_items:
            if filing_description:
                filing_description += ','
            filing_description += line_item.description
        q_payload = dict(
            specversion='1.x-wip',
            type=message_type,
            source=f'https://api.pay.bcregistry.gov.bc.ca/v1/invoices/{invoice.id}',
            id=invoice.id,
            datacontenttype='application/json',
            data=dict(
                identifier=invoice.business_identifier,
                orderNumber=receipt.receipt_number,
                transactionDateTime=get_local_formatted_date_time(payment_transaction.transaction_end_time),
                transactionAmount=receipt.receipt_amount,
                transactionId=invoice_ref.invoice_number,
                refundDate=get_local_formatted_date_time(datetime.now(), '%Y%m%d'),
                filingDescription=filing_description
            ))
        if invoice.payment_method_code == PaymentMethod.DRAWDOWN.value:
            payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(invoice.payment_account_id)
            q_payload['data'].update(dict(
                bcolAccount=invoice.bcol_account,
                bcolUser=payment_account.bcol_user_id
            ))
        current_app.logger.debug('Publishing payment refund request to mailer ')
        current_app.logger.debug(q_payload)
        publish_response(payload=q_payload, client_name=current_app.config.get('NATS_MAILER_CLIENT_NAME'),
                         subject=current_app.config.get('NATS_MAILER_SUBJECT'))
