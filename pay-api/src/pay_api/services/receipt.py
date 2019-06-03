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

from flask import current_app

from pay_api.models import Receipt as ReceiptModel
from datetime import datetime


class Receipt():  # pylint: disable=too-many-instance-attributes
    """Service to manage Payment Line Item operations."""

    def __init__(self):
        """Return a User Service object."""
        self.__dao = None
        self._id: int = None
        self._invoice_id: int = None
        self._receipt_number: str = None
        self._receipt_date: datetime = None
        self._receipt_amount: float = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = ReceiptModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.invoice_id: int = self._dao.invoice_id
        self.receipt_number: str = self._dao.receipt_number
        self.receipt_date: datetime = self._dao.receipt_date
        self.receipt_amount: float = self._dao.receipt_amount

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
    def receipt_number(self):
        """Return the _receipt_number."""
        return self._receipt_number

    @receipt_number.setter
    def receipt_number(self, value: str):
        """Set the filing_fees."""
        self._receipt_number = value
        self._dao.receipt_number = value

    @property
    def receipt_date(self):
        """Return the _receipt_date."""
        return self._receipt_date

    @receipt_date.setter
    def receipt_date(self, value: datetime):
        """Set the receipt_date."""
        self._receipt_date = value
        self._dao.receipt_date = value

    @property
    def receipt_amount(self):
        """Return the _receipt_amount."""
        return self._receipt_amount

    @receipt_amount.setter
    def receipt_amount(self, value: int):
        """Set the receipt_amount."""
        self._receipt_amount = value
        self._dao.receipt_amount = value

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    @staticmethod
    def find_by_id(receipt_id: int):
        receipt_dao = ReceiptModel.find_by_id(receipt_id)

        receipt = Receipt()
        receipt._dao = receipt_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return receipt

    @staticmethod
    def find_by_invoice_id_and_receipt_number(invoice_id: int, receipt_number: str = None):
        receipt_dao = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice_id, receipt_number)

        receipt = Receipt()
        receipt._dao = receipt_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_invoice_id_and_receipt_number')
        return receipt
