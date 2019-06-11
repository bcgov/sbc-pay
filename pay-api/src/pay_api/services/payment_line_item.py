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
"""Service to manage Payment Line Items."""

from flask import current_app

from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.services.fee_schedule import FeeSchedule
from pay_api.utils.enums import Status


class PaymentLineItem:  # pylint: disable=too-many-instance-attributes
    """Service to manage Payment Line Item operations."""

    def __init__(self):
        """Return a User Service object."""
        self.__dao = None
        self._id: int = None
        self._invoice_id: int = None
        self._filing_fees: float = None
        self._fee_schedule_id: int = None
        self._processing_fees: float = None
        self._service_fees: float = None
        self._description: str = None
        self._gst: float = None
        self._pst: float = None
        self._total: float = None
        self._quantity: int = None
        self._line_item_status_code: str = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = PaymentLineItemModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.invoice_id: int = self._dao.invoice_id
        self.filing_fees: float = self._dao.filing_fees
        self.fee_schedule_id: int = self._dao.fee_schedule_id
        self.processing_fees: float = self._dao.processing_fees
        self.service_fees: float = self._dao.service_fees
        self.description: str = self._dao.description
        self.gst: float = self._dao.gst
        self.pst: float = self._dao.pst
        self.total: float = self._dao.total
        self.quantity: int = self._dao.quantity
        self._line_item_status_code: str = self._dao.line_item_status_code

    @property
    def id(self):
        """Return the _id."""
        return self._id

    @id.setter
    def id(self, value: int):
        """Set the id."""
        self._id = value
        self._dao.id = value

    @property
    def invoice_id(self):
        """Return the _invoice_id."""
        return self._invoice_id

    @invoice_id.setter
    def invoice_id(self, value: int):
        """Set the invoice_id."""
        self._invoice_id = value
        self._dao.invoice_id = value

    @property
    def filing_fees(self):
        """Return the _filing_fees."""
        return self._filing_fees

    @filing_fees.setter
    def filing_fees(self, value: float):
        """Set the filing_fees."""
        self._filing_fees = value
        self._dao.filing_fees = value

    @property
    def fee_schedule_id(self):
        """Return the _fee_schedule_id."""
        return self._fee_schedule_id

    @fee_schedule_id.setter
    def fee_schedule_id(self, value: int):
        """Set the fee_schedule_id."""
        self._fee_schedule_id = value
        self._dao.fee_schedule_id = value

    @property
    def processing_fees(self):
        """Return the _processing_fees."""
        return self._processing_fees

    @processing_fees.setter
    def processing_fees(self, value: float):
        """Set the processing_fees."""
        self._processing_fees = value
        self._dao.processing_fees = value

    @property
    def service_fees(self):
        """Return the _service_fees."""
        return self._service_fees

    @service_fees.setter
    def service_fees(self, value: float):
        """Set the service_fees."""
        self._service_fees = value
        self._dao.service_fees = value

    @property
    def description(self):
        """Return the _description."""
        return self._description

    @description.setter
    def description(self, value: str):
        """Set the description."""
        self._description = value
        self._dao.description = value

    @property
    def gst(self):
        """Return the _gst."""
        return self._gst

    @gst.setter
    def gst(self, value: float):
        """Set the gst."""
        self._gst = value
        self._dao.gst = value

    @property
    def pst(self):
        """Return the _pst."""
        return self._pst

    @pst.setter
    def pst(self, value: float):
        """Set the pst."""
        self._pst = value
        self._dao.pst = value

    @property
    def total(self):
        """Return the _total."""
        return self._total

    @total.setter
    def total(self, value: float):
        """Set the total."""
        self._total = value
        self._dao.total = value

    @property
    def quantity(self):
        """Return the _quantity."""
        return self._quantity

    @quantity.setter
    def quantity(self, value: int):
        """Set the quantity."""
        self._quantity = value
        self._dao.quantity = value

    @property
    def line_item_status_code(self):
        """Return the line_item_status_code."""
        return self._line_item_status_code

    @line_item_status_code.setter
    def line_item_status_code(self, value: str):
        """Set the line_item_status_code."""
        self._line_item_status_code = value
        self._dao.line_item_status_code = value

    @staticmethod
    def populate(value):
        line_item: PaymentLineItem = PaymentLineItem()
        line_item._dao = value
        return line_item

    def asdict(self):
        """Return the invoice as a python dict."""
        d = {
            'id': self._id,
            'invoice_id': self._invoice_id,
            'filing_fees': self._filing_fees,
            'fee_schedule_id': self._fee_schedule_id,
            'quantity': self._quantity,
            'processing_fees': self._processing_fees,
            'service_fees': self._service_fees,
            'description': self._description,
            'gst': self._gst,
            'pst': self._pst,
            'total': self._total,
            'line_item_status_code': self.line_item_status_code,
        }
        return d

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    @staticmethod
    def create(invoice_id: int, fee: FeeSchedule):
        """Create Payment Line Item record."""
        current_app.logger.debug('<create')
        p = PaymentLineItem()
        p.invoice_id = invoice_id
        p.total = fee.total
        p.fee_schedule_id = fee.fee_schedule_id
        p.description = fee.description
        p.filing_fees = fee.fee_amount
        p.gst = fee.gst
        p.processing_fees = fee.processing_fees
        p.pst = fee.pst
        p.service_fees = fee.service_fees
        p.quantity = fee.quantity
        p.line_item_status_code = Status.CREATED.value

        p_dao = p.flush()

        p = PaymentLineItem()
        p._dao = p_dao  # pylint: disable=protected-access

        current_app.logger.debug('>create')
        return p

    @staticmethod
    def find_by_id(line_id: int):
        """Find by line id."""
        line_dao = PaymentLineItemModel.find_by_id(line_id)

        line = PaymentLineItem()
        line._dao = line_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return line
