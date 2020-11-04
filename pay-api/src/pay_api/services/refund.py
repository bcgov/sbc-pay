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
from typing import Dict
from typing import Optional

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import Refund as RefundModel, Invoice as InvoiceModel, Payment as PaymentModel
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, PaymentStatus
from pay_api.utils.errors import Error
from pay_api.utils.user_context import user_context


class RefundService:  # pylint: disable=too-many-instance-attributes
    """Service to hold and manage refund instance."""

    def __init__(self):
        """Return a refund object."""
        self.__dao: Optional[RefundModel] = None
        self._id: Optional[int] = None
        self._invoice_id: Optional[int] = None
        self._requested_date: Optional[datetime] = None
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
        self.requested_date: datetime = self._dao.requested_date
        self.reason: str = self._dao.reason
        self.requested_by: str = self._dao.requested_by

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
    def requested_date(self) -> datetime:
        """Return the requested_date."""
        return self._requested_date

    @requested_date.setter
    def requested_date(self, value: datetime):
        """Set the filing_fees."""
        self._requested_date = value
        self._dao.requested_date = value

    @property
    def reason(self) -> Optional[str]:
        """Return the _reason."""
        return self._reason

    @reason.setter
    def reason(self, value: datetime):
        """Set the reason."""
        self._reason = value
        self._dao.reason = value

    @property
    def requested_by(self) -> Optional[str]:
        """Return the requested_by."""
        return self.requested_by

    @requested_by.setter
    def requested_by(self, value: str):
        """Set the reason."""
        self._requested_by = value
        self._dao.requested_by = value

    def save(self) -> RefundModel:
        """Save the information to the DB and commit."""
        return self._dao.save()

    def flush(self) -> RefundModel:
        """Save the information to the DB and flush."""
        return self._dao.flush()

    @staticmethod
    @user_context
    def create_refund(invoice_id: int, request: Dict[str, str], **kwargs):
        """Create refund."""
        current_app.logger.debug('<create refund')
        # Do validation by looking up the invoice
        invoice: InvoiceModel = InvoiceModel.find_by_id(invoice_id)
        # Allow refund only for direct pay payments, and only if the status of invoice is PAID/UPDATE_REVENUE_ACCOUNT
        paid_statuses = (InvoiceStatus.PAID.value, InvoiceStatus.UPDATE_REVENUE_ACCOUNT.value)

        if invoice.payment_method_code != PaymentMethod.DIRECT_PAY.value \
                or invoice.invoice_status_code not in paid_statuses:
            raise BusinessException(Error.INVALID_REQUEST)

        refund: RefundService = RefundService()
        refund.invoice_id = invoice_id
        refund.reason = request.get('refund', None)
        refund.requested_by = kwargs['user'].user_name
        refund.requested_date = datetime.now()
        refund.flush()

        # set invoice status
        invoice.invoice_status_code = InvoiceStatus.REFUND_REQUESTED.value
        invoice.flush()
        payment: PaymentModel = PaymentModel.find_payment_for_invoice(invoice_id)
        payment.payment_status_code = PaymentStatus.REFUNDED.value
        payment.save()
