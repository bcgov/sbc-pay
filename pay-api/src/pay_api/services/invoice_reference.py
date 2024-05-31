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
"""Service to manage Invoice Reference."""

from flask import current_app

from pay_api.models import InvoiceReference as ReferenceModel
from pay_api.utils.enums import InvoiceReferenceStatus


class InvoiceReference:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """Service to manage Invoice Reference related operations."""

    def __init__(self):
        """Initialize the service."""
        self.__dao = None
        self._id: int = None
        self._invoice_id: int = None
        self._invoice_number: str = None
        self._reference_number: str = None
        self._status_code: str = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = ReferenceModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.invoice_id: int = self._dao.invoice_id
        self.invoice_number: str = self._dao.invoice_number
        self.reference_number: str = self._dao.reference_number
        self.status_code: str = self._dao.status_code

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
    def status_code(self):
        """Return the status_code."""
        return self._status_code

    @status_code.setter
    def status_code(self, value: str):
        """Set the status_code."""
        self._status_code = value
        self._dao.status_code = value

    @property
    def invoice_id(self):
        """Return the invoice_id."""
        return self._invoice_id

    @invoice_id.setter
    def invoice_id(self, value: int):
        """Set the invoice_id."""
        self._invoice_id = value
        self._dao.invoice_id = value

    def save(self):
        """Save the information to the DB and commit."""
        return self._dao.save()

    def flush(self):
        """Save the information to the DB and flush."""
        return self._dao.flush()

    @staticmethod
    def create(invoice_id: int, invoice_number: str, reference_number: str):
        """Create invoice reference record."""
        current_app.logger.debug('<create')
        i = InvoiceReference()
        i.invoice_id = invoice_id
        i.status_code = InvoiceReferenceStatus.ACTIVE.value
        i.invoice_number = invoice_number
        i.reference_number = reference_number

        i._dao = i.save()  # pylint: disable=protected-access
        current_app.logger.debug('>create')
        return i

    @staticmethod
    def find_active_reference_by_invoice_id(inv_id: int):
        """Find invoice reference by invoice id."""
        ref_dao = ReferenceModel.find_by_invoice_id_and_status(inv_id, InvoiceReferenceStatus.ACTIVE.value)
        invoice_reference = None
        if ref_dao:
            invoice_reference = InvoiceReference()
            invoice_reference._dao = ref_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_reference_by_invoice_id')
        return invoice_reference

    @staticmethod
    def find_completed_reference_by_invoice_id(inv_id: int):
        """Find invoice reference by invoice id."""
        ref_dao = ReferenceModel.find_by_invoice_id_and_status(inv_id, InvoiceReferenceStatus.COMPLETED.value)
        invoice_reference = InvoiceReference()
        invoice_reference._dao = ref_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_reference_by_invoice_id')
        return invoice_reference

    @staticmethod
    def find_any_active_reference_by_invoice_number(inv_number: str):
        """Find invoice reference by invoice id."""
        ref_dao = ReferenceModel.find_any_active_reference_by_invoice_number(inv_number)
        invoice_reference = InvoiceReference()
        invoice_reference._dao = ref_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_any_active_reference_by_invoice_number')
        return invoice_reference
