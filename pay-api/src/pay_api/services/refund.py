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
"""Service to manage Receipt."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.factory.payment_system_factory import PaymentSystemFactory
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import Refund as RefundModel
from pay_api.models import RefundsPartial as RefundPartialModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import db
from pay_api.models import RefundPartialLine
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.flags import flags
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.constants import REFUND_SUCCESS_MESSAGES
from pay_api.utils.converter import Converter
from pay_api.utils.enums import InvoiceStatus, Role, RoutingSlipStatus
from pay_api.utils.errors import Error
from pay_api.utils.user_context import UserContext, user_context
from pay_api.utils.util import get_quantized, get_str_by_path


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
        self._decision_made_by: Optional[str] = None
        self._decision_date: Optional[datetime] = None

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
        self.decision_made_by: str = self._dao.decision_made_by
        self.decision_date: datetime = self._dao.decision_date

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
    def decision_date(self) -> datetime:
        """Return the decision_date."""
        return self._decision_date

    @decision_date.setter
    def decision_date(self, value: datetime):
        """Set the decision_date."""
        self._decision_date = value
        self._dao.decision_date = value

    @property
    def details(self):
        """Return the details."""
        return self._details

    @details.setter
    def details(self, value: str):
        """Set the details."""
        self._details = value
        self._dao.details = value

    @property
    def decision_made_by(self) -> Optional[str]:
        """Return the decision_made_by."""
        return self.decision_made_by

    @decision_made_by.setter
    def decision_made_by(self, value: str):
        """Set the decision_made_by."""
        self._decision_made_by = value
        self._dao.decision_made_by = value

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
        current_app.logger.debug("<create Routing slip  refund")
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
        reason = get_str_by_path(request, "reason")
        if (refund_status := get_str_by_path(request, "status")) is None:
            raise BusinessException(Error.INVALID_REQUEST)
        user_name = kwargs["user"].user_name
        if get_quantized(rs_model.remaining_amount) == 0:
            raise BusinessException(Error.INVALID_REQUEST)  # refund not possible for zero amount routing slips

        is_refund_finalized = refund_status in (
            RoutingSlipStatus.REFUND_AUTHORIZED.value,
            RoutingSlipStatus.REFUND_REJECTED.value,
        )
        if is_refund_finalized:
            RefundService._is_authorised_refund()

        # Rejected refund makes routing slip active
        if refund_status == RoutingSlipStatus.REFUND_REJECTED.value:
            refund_status = RoutingSlipStatus.ACTIVE.value
            reason = f"Refund Rejected by {user_name}"

        rs_model.status = refund_status
        rs_model.flush()

        refund: RefundService = RefundService()
        refund_dao = RefundModel.find_by_routing_slip_id(rs_model.id)
        if refund_dao:
            refund._dao = refund_dao

        if not is_refund_finalized:
            # do not update these for approval/rejections
            refund.routing_slip_id = rs_model.id
            refund.requested_by = kwargs["user"].user_name
            refund.requested_date = datetime.now(tz=timezone.utc)
        else:
            refund.decision_made_by = kwargs["user"].user_name
            refund.decision_date = datetime.now(tz=timezone.utc)

        refund.reason = reason
        if details := request.get("details"):
            refund.details = details

        refund.save()
        message = REFUND_SUCCESS_MESSAGES.get(f"ROUTINGSLIP.{rs_model.status}")
        return {"message": message}

    @staticmethod
    @user_context
    def _is_authorised_refund(**kwargs):
        user: UserContext = kwargs["user"]
        has_refund_approver_role = Role.FAS_REFUND_APPROVER.value in user.roles
        if not has_refund_approver_role:
            raise BusinessException(Error.INVALID_REQUEST)

    @classmethod
    @user_context
    def create_refund(cls, invoice_id: int, request: Dict[str, str], **kwargs) -> Dict[str, str]:
        """Create refund."""
        current_app.logger.debug(f"Starting refund : {invoice_id}")
        # Do validation by looking up the invoice
        invoice: InvoiceModel = InvoiceModel.find_by_id(invoice_id)

        paid_statuses = (
            InvoiceStatus.PAID.value,
            InvoiceStatus.APPROVED.value,
            InvoiceStatus.UPDATE_REVENUE_ACCOUNT.value,
        )

        if invoice.invoice_status_code not in paid_statuses:
            current_app.logger.info(f"Cannot process refund as status of {invoice_id} is {invoice.invoice_status_code}")
            raise BusinessException(Error.INVALID_REQUEST)

        refund: RefundService = RefundService()
        refund.invoice_id = invoice_id
        refund.reason = get_str_by_path(request, "reason")
        refund.requested_by = kwargs["user"].user_name
        refund.requested_date = datetime.now(tz=timezone.utc)
        pay_system_service: PaymentSystemService = PaymentSystemFactory.create_from_payment_method(
            payment_method=invoice.payment_method_code
        )
        payment_account = PaymentAccount.find_by_id(invoice.payment_account_id)
        refund_revenue = (request or {}).get("refundRevenue", None)
        if refund_revenue and not flags.is_on("enable-partial-refunds", default=False):
            raise BusinessException(Error.INVALID_REQUEST)
        refund_partial_lines = cls._get_partial_refund_lines(refund_revenue)
        invoice_status = pay_system_service.process_cfs_refund(
            invoice,
            payment_account=payment_account,
            refund_partial=refund_partial_lines,
        )
        refund.flush()
        cls._save_partial_refund_lines(refund_partial_lines)
        message = REFUND_SUCCESS_MESSAGES.get(f"{invoice.payment_method_code}.{invoice.invoice_status_code}")
        # set invoice status
        invoice.invoice_status_code = invoice_status or InvoiceStatus.REFUND_REQUESTED.value
        invoice.refund = invoice.total  # no partial refund
        if invoice.invoice_status_code in (
            InvoiceStatus.REFUNDED.value,
            InvoiceStatus.CANCELLED.value,
            InvoiceStatus.CREDITED.value,
        ):
            invoice.refund_date = datetime.now(tz=timezone.utc)
        invoice.save()
        current_app.logger.debug(f"Completed refund : {invoice_id}")
        return {"message": message}

    @staticmethod
    def _save_partial_refund_lines(partial_refund_lines: List[RefundPartialLine]):
        """Persist a list of partial refund lines."""
        for line in partial_refund_lines:
            refund_line = RefundPartialModel(
                payment_line_item_id=line.payment_line_item_id,
                refund_amount=line.refund_amount,
                refund_type=line.refund_type,
            )
            db.session.add(refund_line)

    @staticmethod
    def _get_partial_refund_lines(
        refund_revenue: List[Dict],
    ) -> List[RefundPartialLine]:
        """Convert Refund revenue data to a list of Partial Refund lines."""
        if not refund_revenue:
            return []

        return Converter(camel_to_snake_case=True, enum_to_value=True).structure(
            refund_revenue, List[RefundPartialLine]
        )

    @staticmethod
    def get_refund_partials_by_invoice_id(invoice_id: int):
        """Return refund partials by invoice id."""
        return (
            db.session.query(RefundPartialModel)
            .join(
                PaymentLineItemModel,
                PaymentLineItemModel.id == RefundPartialModel.payment_line_item_id,
            )
            .filter(PaymentLineItemModel.invoice_id == invoice_id)
            .all()
        )

    @staticmethod
    def get_refund_partials_by_payment_line_item_id(payment_line_item_id: int):
        """Return refund partials by payment line item id."""
        return db.session.query(RefundPartialModel).filter(PaymentLineItemModel.id == payment_line_item_id).all()
