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
"""Service to manage Invoice."""
from __future__ import annotations

from datetime import datetime

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceSchema
from pay_api.services.auth import check_auth
from pay_api.utils.constants import ALL_ALLOWED_ROLES
from pay_api.utils.errors import Error
from pay_api.utils.enums import InvoiceStatus, PaymentStatus


class Invoice:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """Service to manage Invoice related operations."""

    def __init__(self):
        """Initialize the service."""
        self.__dao = None
        self._id: int = None
        self._invoice_status_code: str = None
        self._payment_account_id: str = None
        self._bcol_account: str = None
        self._total: float = None
        self._paid: float = None
        self._refund: float = None
        self._payment_date: datetime = None
        self._payment_line_items = None
        self._corp_type_code = None
        self._receipts = None
        self._routing_slip: str = None
        self._filing_id: str = None
        self._folio_number: str = None
        self._service_fees: float = None
        self._business_identifier: str = None
        self._dat_number: str = None
        self._cfs_account_id: int
        self._payment_method_code: str = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = InvoiceModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.payment_method_code: int = self._dao.payment_method_code
        self.invoice_status_code: str = self._dao.invoice_status_code
        self.bcol_account: str = self._dao.bcol_account
        self.payment_account_id: str = self._dao.payment_account_id
        self.refund: float = self._dao.refund
        self.payment_date: datetime = self._dao.payment_date
        self.total: float = self._dao.total
        self.paid: float = self._dao.paid
        self.payment_line_items = self._dao.payment_line_items
        self.corp_type_code = self._dao.corp_type_code
        self.receipts = self._dao.receipts
        self.routing_slip: str = self._dao.routing_slip
        self.filing_id: str = self._dao.filing_id
        self.folio_number: str = self._dao.folio_number
        self.service_fees: float = self._dao.service_fees
        self.business_identifier: str = self._dao.business_identifier
        self.dat_number: str = self._dao.dat_number
        self.cfs_account_id: int = self._dao.cfs_account_id

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
    def payment_method_code(self):
        """Return the payment_method_code."""
        return self._payment_method_code

    @payment_method_code.setter
    def payment_method_code(self, value: str):
        """Set the payment_method_code."""
        self._payment_method_code = value
        self._dao.payment_method_code = value

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
    def payment_account_id(self):
        """Return the payment_account_id."""
        return self._payment_account_id

    @payment_account_id.setter
    def payment_account_id(self, value: str):
        """Set the payment_account_id."""
        self._payment_account_id = value
        self._dao.payment_account_id = value

    @property
    def bcol_account(self):
        """Return the bcol_account."""
        return self._bcol_account

    @bcol_account.setter
    def bcol_account(self, value: str):
        """Set the bcol_account."""
        self._bcol_account = value
        self._dao.bcol_account = value

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
    def payment_line_items(self):
        """Return the payment payment_line_items."""
        return self._payment_line_items

    @payment_line_items.setter
    def payment_line_items(self, value):
        """Set the payment_line_items."""
        self._payment_line_items = value
        self._dao.payment_line_items = value

    @property
    def corp_type_code(self):
        """Return the corp_type_code."""
        return self._corp_type_code

    @corp_type_code.setter
    def corp_type_code(self, value):
        """Set the corp_type_code."""
        self._corp_type_code = value
        self._dao.corp_type_code = value

    @property
    def receipts(self):
        """Return the receipts."""
        return self._receipts

    @receipts.setter
    def receipts(self, value):
        """Set the receipts."""
        self._receipts = value
        self._dao.receipts = value

    @property
    def routing_slip(self):
        """Return the routing_slip."""
        return self._routing_slip

    @routing_slip.setter
    def routing_slip(self, value: str):
        """Set the routing_slip."""
        self._routing_slip = value
        self._dao.routing_slip = value

    @property
    def filing_id(self):
        """Return the filing_id."""
        return self._filing_id

    @filing_id.setter
    def filing_id(self, value: str):
        """Set the filing_id."""
        self._filing_id = value
        self._dao.filing_id = value

    @property
    def folio_number(self):
        """Return the folio_number."""
        return self._folio_number

    @folio_number.setter
    def folio_number(self, value: str):
        """Set the folio_number."""
        self._folio_number = value
        self._dao.folio_number = value

    @property
    def service_fees(self):
        """Return the service_fees."""
        return self._service_fees

    @service_fees.setter
    def service_fees(self, value: float):
        """Set the service_fees."""
        self._service_fees = value
        self._dao.service_fees = value

    @property
    def business_identifier(self):
        """Return the business_identifier."""
        return self._business_identifier

    @business_identifier.setter
    def business_identifier(self, value: int):
        """Set the business_identifier."""
        self._business_identifier = value
        self._dao.business_identifier = value

    @property
    def dat_number(self):
        """Return the dat_number."""
        return self._dat_number

    @dat_number.setter
    def dat_number(self, value: str):
        """Set the dat_number."""
        self._dat_number = value
        self._dao.dat_number = value

    @property
    def cfs_account_id(self):
        """Return the cfs_account_id."""
        return self._cfs_account_id

    @cfs_account_id.setter
    def cfs_account_id(self, value: int):
        """Set the cfs_account_id."""
        self._cfs_account_id = value
        self._dao.cfs_account_id = value

    def commit(self):
        """Save the information to the DB."""
        return self._dao.commit()

    def rollback(self):
        """Rollback."""
        return self._dao.rollback()

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    def asdict(self):
        """Return the invoice as a python dict."""
        invoice_schema = InvoiceSchema()
        d = invoice_schema.dump(self._dao)
        # TODO remove it later, adding this here to make non-breaking changes for other teams
        if d.get('status_code') == InvoiceStatus.PAID.value:
            d['status_code'] = PaymentStatus.COMPLETED.value

        return d

    @staticmethod
    def populate(value):
        """Populate invoice service."""
        invoice: Invoice = Invoice()
        invoice._dao = value  # pylint: disable=protected-access
        return invoice

    @staticmethod
    def find_by_id(identifier: int, skip_auth_check: bool = False, one_of_roles=ALL_ALLOWED_ROLES):
        """Find invoice by id."""
        invoice_dao = InvoiceModel.find_by_id(identifier)

        if not invoice_dao:
            raise BusinessException(Error.INVALID_INVOICE_ID)

        if not skip_auth_check:
            Invoice._check_for_auth(invoice_dao, one_of_roles)

        invoice = Invoice()
        invoice._dao = invoice_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return invoice

    @staticmethod
    def find_invoices_for_payment(payment_id: int) -> [Invoice]:
        """Find invoices by payment id."""
        invoices: [Invoice] = []
        invoice_daos: [InvoiceModel] = InvoiceModel.find_invoices_for_payment(payment_id)

        for invoice_dao in invoice_daos:
            invoice = Invoice()
            invoice._dao = invoice_dao  # pylint: disable=protected-access
            invoices.append(invoice)

        current_app.logger.debug('>find_by_id')
        return invoices

    @staticmethod
    def _check_for_auth(dao, one_of_roles=ALL_ALLOWED_ROLES):
        # Check if user is authorized to perform this action
        check_auth(dao.business_identifier, one_of_roles=one_of_roles)
