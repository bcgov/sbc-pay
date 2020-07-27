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

from datetime import datetime

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceSchema
from pay_api.services.auth import check_auth
from pay_api.services.fee_schedule import FeeSchedule
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.constants import ALL_ALLOWED_ROLES
from pay_api.utils.enums import PaymentSystem, InvoiceStatus
from pay_api.utils.errors import Error


class Invoice:  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """Service to manage Invoice related operations."""

    def __init__(self):
        """Initialize the service."""
        self.__dao = None
        self._id: int = None
        self._payment_id: int = None
        self._invoice_status_code: str = None
        self._credit_account_id: str = None
        self._bcol_account_id: str = None
        self._internal_account_id: str = None
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
        self.invoice_status_code: str = self._dao.invoice_status_code
        self.bcol_account_id: str = self._dao.bcol_account_id
        self.credit_account_id: str = self._dao.credit_account_id
        self.internal_account_id: str = self._dao.internal_account_id
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
    def invoice_status_code(self):
        """Return the invoice_status_code."""
        return self._invoice_status_code

    @invoice_status_code.setter
    def invoice_status_code(self, value: str):
        """Set the invoice_status_code."""
        self._invoice_status_code = value
        self._dao.invoice_status_code = value

    @property
    def credit_account_id(self):
        """Return the credit_account_id."""
        return self._credit_account_id

    @credit_account_id.setter
    def credit_account_id(self, value: str):
        """Set the credit_account_id."""
        self._credit_account_id = value
        self._dao.credit_account_id = value

    @property
    def bcol_account_id(self):
        """Return the bcol_account_id."""
        return self._bcol_account_id

    @bcol_account_id.setter
    def bcol_account_id(self, value: str):
        """Set the bcol_account_id."""
        self._bcol_account_id = value
        self._dao.bcol_account_id = value

    @property
    def internal_account_id(self):
        """Return the internal_account_id."""
        return self._internal_account_id

    @internal_account_id.setter
    def internal_account_id(self, value: str):
        """Set the internal_account_id."""
        self._internal_account_id = value
        self._dao.internal_account_id = value

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

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    def asdict(self):
        """Return the invoice as a python dict."""
        invoice_schema = InvoiceSchema()
        d = invoice_schema.dump(self._dao)

        return d

    @staticmethod
    def populate(value):
        """Populate invoice service."""
        invoice: Invoice = Invoice()
        invoice._dao = value  # pylint: disable=protected-access
        return invoice

    @staticmethod
    def create(account: PaymentAccount, payment_id: int, fees: [FeeSchedule], corp_type: str, **kwargs):
        """Create invoice record."""
        current_app.logger.debug('<create')
        i = Invoice()
        i.payment_id = payment_id
        i.invoice_status_code = InvoiceStatus.CREATED.value
        if account.payment_system_code == PaymentSystem.BCOL.value:
            i.bcol_account_id = account.id
        elif account.payment_system_code == PaymentSystem.PAYBC.value:
            i.credit_account_id = account.id
        elif account.payment_system_code == PaymentSystem.INTERNAL.value:
            i.internal_account_id = account.id

        total_excluding_service_fee = sum(fee.total_excluding_service_fees for fee in fees) if fees else 0
        #   TODO Change based on decision, whether to apply service fees for each line ot not.
        #   For now add up the service fee on each fee schedule

        i.service_fees = sum(fee.service_fees for fee in fees) if fees else 0

        i.total = i.service_fees + total_excluding_service_fee
        i.paid = 0
        i.refund = 0
        i.routing_slip = kwargs.get('routing_slip', None)
        i.filing_id = kwargs.get('filing_id', None)
        i.folio_number = kwargs.get('folio_number', None)
        i.business_identifier = kwargs.get('business_identifier', None)
        i.corp_type_code = corp_type
        i.dat_number = kwargs.get('dat_number', None)

        i._dao = i.flush()  # pylint: disable=protected-access
        current_app.logger.debug('>create')
        return i

    @staticmethod
    def find_by_id(identifier: int, pay_id: int = None, skip_auth_check: bool = False):
        """Find invoice by id."""
        invoice_dao = InvoiceModel.find_by_id(identifier) if not pay_id else InvoiceModel.find_by_id_and_payment_id(
            identifier, pay_id)
        if not invoice_dao:
            raise BusinessException(Error.INVALID_INVOICE_ID)

        if not skip_auth_check:
            Invoice._check_for_auth(invoice_dao)

        invoice = Invoice()
        invoice._dao = invoice_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return invoice

    @staticmethod
    def find_by_payment_identifier(identifier: int, skip_auth_check: bool = False):
        """Find invoice by payment identifier."""
        invoice_dao = InvoiceModel.find_by_payment_id(identifier)

        if not skip_auth_check:
            Invoice._check_for_auth(invoice_dao)

        invoice = Invoice()
        invoice._dao = invoice_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return invoice

    @staticmethod
    def get_invoices(payment_identifier: str, skip_auth_check: bool = False):
        """Find invoices."""
        current_app.logger.debug('<get_invoices')

        data = {'items': []}
        daos = [InvoiceModel.find_by_payment_id(payment_identifier)]  # Treating as a set to avoid re-work in future
        for dao in daos:
            if dao:
                if not skip_auth_check:
                    Invoice._check_for_auth(dao)
                data['items'].append(Invoice.populate(dao).asdict())

        current_app.logger.debug('>get_invoices')
        return data

    @staticmethod
    def _check_for_auth(dao):
        # Check if user is authorized to perform this action
        check_auth(dao.business_identifier, one_of_roles=ALL_ALLOWED_ROLES)
