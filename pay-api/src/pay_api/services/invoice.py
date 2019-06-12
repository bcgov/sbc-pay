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
"""Service to manage Fee Calculation."""

from datetime import datetime

from flask import current_app

from pay_api.models import Invoice as InvoiceModel
from pay_api.services.fee_schedule import FeeSchedule
from pay_api.services.payment_account import PaymentAccount
from pay_api.services.payment_line_item import PaymentLineItem
from pay_api.utils.enums import Status


class Invoice():  # pylint: disable=too-many-instance-attributes
    """Service to manage Invoice related operations."""

    def __init__(self):
        """Return a User Service object."""
        self.__dao = None
        self._id: int = None
        self._payment_id: int = None
        self._invoice_number: str = None
        self._reference_number: str = None
        self._invoice_status_code: str = None
        self._account_id: str = None
        self._total: float = None
        self._paid: float = None
        self._refund: float = None
        self._payment_date: datetime = None
        self._created_by: str = None
        self._created_on: datetime = None
        self._updated_by: str = None
        self._updated_on: datetime = None
        self._payment_line_items = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = InvoiceModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.payment_id: int = self._dao.payment_id
        self.invoice_number: str = self._dao.invoice_number
        self.reference_number: str = self._dao.reference_number
        self.invoice_status_code: str = self._dao.invoice_status_code
        self.account_id: str = self._dao.account_id
        self.refund: float = self._dao.refund
        self.payment_date: datetime = self._dao.payment_date

        self.total: float = self._dao.total
        self.paid: float = self._dao.paid
        self.created_by: str = self._dao.created_by
        self.created_on: datetime = self._dao.created_on
        self.updated_by: str = self._dao.updated_by
        self.updated_on: datetime = self._dao.updated_on
        self.payment_line_items = self._dao.payment_line_items

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
    def payment_id(self):
        """Return the payment_id."""
        return self._payment_id

    @payment_id.setter
    def payment_id(self, value: int):
        """Set the payment_id."""
        self._payment_id = value
        self._dao.payment_id = value

    @property
    def invoice_number(self):
        """Return the payment_method_code."""
        return self._invoice_number

    @invoice_number.setter
    def invoice_number(self, value: str):
        """Set the invoice_number."""
        self._invoice_number = value
        self._dao.invoice_number = value

    @property
    def reference_number(self):
        """Return the reference_number."""
        return self._reference_number

    @reference_number.setter
    def reference_number(self, value: str):
        """Set the reference_number."""
        self._reference_number = value
        self._dao.reference_number = value

    @property
    def invoice_status_code(self):
        """Return the invoice_status_code."""
        return self._invoice_status_code

    @invoice_status_code.setter
    def invoice_status_code(self, value: str):
        """Set the invoice_status_code."""
        self._invoice_status_code = value
        self._dao.invoice_status_code = value

    @property
    def account_id(self):
        """Return the account_id."""
        return self._account_id

    @account_id.setter
    def account_id(self, value: str):
        """Set the account_id."""
        self._account_id = value
        self._dao.account_id = value

    @property
    def refund(self):
        """Return the refund."""
        return self._refund

    @refund.setter
    def refund(self, value: float):
        """Set the refund."""
        self._refund = value
        self._dao.refund = value

    @property
    def payment_date(self):
        """Return the payment_date."""
        return self._payment_date

    @payment_date.setter
    def payment_date(self, value: datetime):
        """Set the payment_date."""
        self._payment_date = value
        self._dao.payment_date = value

    @property
    def total(self):
        """Return the total."""
        return self._total

    @total.setter
    def total(self, value: float):
        """Set the fee_start_date."""
        self._total = value
        self._dao.total = value

    @property
    def paid(self):
        """Return the paid."""
        return self._paid

    @paid.setter
    def paid(self, value: float):
        """Set the paid."""
        self._paid = value
        self._dao.paid = value

    @property
    def created_by(self):
        """Return the created_by."""
        return self._created_by

    @created_by.setter
    def created_by(self, value: str):
        """Set the created_by."""
        self._created_by = value
        self._dao.created_by = value

    @property
    def created_on(self):
        """Return the created_on."""
        return self._created_on if self._created_on is not None else datetime.now()

    @created_on.setter
    def created_on(self, value: datetime):
        """Set the created_on."""
        self._created_on = value
        self._dao.created_on = value

    @property
    def updated_by(self):
        """Return the updated_by."""
        return self._updated_by

    @updated_by.setter
    def updated_by(self, value: str):
        """Set the created_by."""
        self._updated_by = value
        self._dao.updated_by = value

    @property
    def updated_on(self):
        """Return the updated_on."""
        return self._updated_on

    @updated_on.setter
    def updated_on(self, value: datetime):
        """Set the updated_on."""
        self._updated_on = value
        self._dao.updated_on = value

    @property
    def payment_line_items(self):
        """Return the payment invoices."""
        return self._payment_line_items

    @payment_line_items.setter
    def payment_line_items(self, value):
        """Set the invoices."""
        self._payment_line_items = value
        self._dao.payment_line_items = value

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    def asdict(self):
        """Return the invoice as a python dict."""
        payment_line_items = []
        for payment_line_item in self._payment_line_items:
            payment_line_items.append(PaymentLineItem.populate(payment_line_item).asdict())

        d = {
            'id': self._id,
            'created_by': self._created_by,
            'created_on': self._created_on,
            'updated_by': self._updated_by,
            'updated_on': self._updated_on,
            'invoice_number': self._invoice_number,
            'reference_number': self._reference_number,
            'invoice_status': self._invoice_status_code,
            'account_id': self._account_id,
            'payment_id': self._payment_id,
            'payment_date': self._payment_date,
            'total': self._total,
            'paid': self._paid,
            'refund': self._refund,
            'line_items': payment_line_items
        }

        return d

    @staticmethod
    def populate(value):
        """Populate Invoice."""
        invoice: Invoice = Invoice()
        invoice._dao = value   # pylint: disable=protected-access
        return invoice

    @staticmethod
    def create(account: PaymentAccount, payment_id: int, fees: [FeeSchedule], current_user: str):
        """Create invoice record."""
        current_app.logger.debug('<create')
        i = Invoice()
        i.created_on = datetime.now()
        i.created_by = current_user
        i.payment_id = payment_id
        i.invoice_status_code = Status.DRAFT.value
        i.account_id = account.id
        i.total = sum(fee.total for fee in fees)
        i.paid = 0
        i.payment_date = None  # TODO
        i.refund = 0

        i._dao = i.flush()  # pylint: disable=protected-access
        current_app.logger.debug('>create')
        return i

    @staticmethod
    def find_by_id(identifier: int):
        """Find invoice by id."""
        invoice_dao = InvoiceModel.find_by_id(identifier)

        invoice = Invoice()
        invoice._dao = invoice_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return invoice

    @staticmethod
    def find_by_payment_identifier(identifier: int):
        """Find invoice by payment identifier."""
        invoice_dao = InvoiceModel.find_by_payment_id(identifier)

        invoice = Invoice()
        invoice._dao = invoice_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return invoice

    @staticmethod
    def find_all_by_payment_identifier(identifier: int):
        """Find invoice by payment identifier."""
        invoice_dao = InvoiceModel.find_all_by_payment_id(identifier)

        invoice = Invoice()
        invoice._dao = invoice_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return invoice
