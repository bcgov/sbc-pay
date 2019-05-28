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

from pay_api.models import PaymentTransaction as PaymentTransactionModel
from .payment import Payment
from pay_api.utils.errors import Error
from pay_api.exceptions import BusinessException
from pay_api.utils.enums import Status, PaymentSystem
from .invoice import InvoiceModel

class PaymentTransaction():  # pylint: disable=too-many-instance-attributes
    """Service to manage Payment transaction operations."""

    def __init__(self):
        """Return a User Service object."""
        self.__dao = None
        self._id: int = None
        self._status_code: str = None
        self._payment_id: int = None
        self._redirect_url: str = None
        self._pay_system_url: str = None
        self._transaction_start_time: datetime = None
        self._transaction_end_time: datetime = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = PaymentTransactionModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.status_code: str = self._dao.status_code
        self.payment_id: int = self._dao.payment_id
        self.redirect_url: str = self._dao.redirect_url
        self.pay_system_url: str = self._dao.pay_system_url
        self.transaction_start_time: datetime = self._dao.transaction_start_time
        self.transaction_end_time: datetime = self._dao.transaction_end_time

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
    def status_code(self):
        """Return the status_code."""
        return self._status_code

    @status_code.setter
    def status_code(self, value: str):
        """Set the payment_id."""
        self._status_code = value
        self._dao.status_code = value

    @property
    def payment_id(self):
        """Return the payment_id."""
        return self._payment_id

    @payment_id.setter
    def payment_id(self, value: int):
        """Set the corp_type_code."""
        self._payment_id = value
        self._dao.payment_id = value

    @property
    def redirect_url(self):
        """Return the redirect_url."""
        return self._redirect_url

    @redirect_url.setter
    def redirect_url(self, value: str):
        """Set the redirect_url."""
        self._redirect_url = value
        self._dao.redirect_url = value

    @property
    def pay_system_url(self):
        """Return the pay_system_url."""
        return self._pay_system_url

    @pay_system_url.setter
    def pay_system_url(self, value: str):
        """Set the account_number."""
        self._pay_system_url = value
        self._dao.pay_system_url = value

    @property
    def transaction_start_time(self):
        """Return the transaction_start_time."""
        return self._transaction_start_time

    @transaction_start_time.setter
    def transaction_start_time(self, value: datetime):
        """Set the transaction_start_time."""
        self._transaction_start_time = value
        self._dao.transaction_start_time = value

    @property
    def transaction_end_time(self):
        """Return the transaction_end_time."""
        return self._transaction_end_time

    @transaction_end_time.setter
    def transaction_end_time(self, value: datetime):
        """Set the transaction_end_time."""
        self._transaction_end_time = value
        self._dao.transaction_end_time = value

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    def asdict(self):
        """Return the transaction as a python dict."""
        d = {
            'id': self._id,
            'payment_id': self._payment_id,
            'redirect_url': self._redirect_url,
            'pay_system_url': self._pay_system_url,
            'status_code': self._status_code,
            'transaction_start_time': self._transaction_start_time
        }
        if self._transaction_start_time:
            d['transaction_end_time'] = self._transaction_end_time
        return d

    def save(self):
        """Save the fee schedule information."""
        self._dao.save()

    @staticmethod
    def create(payment_identifier: str, redirect_uri: str):
        """Create transaction record."""
        current_app.logger.debug('<create transaction')
        # Lookup payment record
        payment: Payment = Payment.find_by_id(payment_identifier)
        if not payment.id:
            raise BusinessException(Error.PAY005)

        transaction = PaymentTransaction()
        transaction.payment_id = payment.id
        transaction.redirect_url = redirect_uri
        transaction.pay_system_url = None  # TODO
        transaction.transaction_start_time = datetime.now()
        transaction.status_code = Status.CREATED
        transaction_dao = transaction.flush()
        transaction._dao = transaction_dao  # pylint: disable=protected-access
        transaction.pay_system_url = transaction.build_pay_system_url(payment)

        transaction = PaymentTransaction()
        transaction._dao = transaction_dao  # pylint: disable=protected-access
        current_app.logger.debug('>create transaction')
        return transaction

    @staticmethod
    def build_pay_system_url(payment: Payment, transaction_id: str):
        current_app.logger.debug('<build_pay_system_url')
        pay_system_url = ''
        if payment.payment_system_code == PaymentSystem.PAYBC.value:
            invoices = InvoiceModel.find_by_payment_id(payment.id)
            if len(invoices) > 1 : #
                raise NotImplementedError
            pay_system_url = current_app.config.get('PAYBC_PORTAL_URL')+'/inv_number={}&pbc_ref_number={}'.format()


        else :
            raise NotImplementedError

        current_app.logger.debug('>build_pay_system_url')
        return pay_system_url

    @staticmethod
    def find_by_id(transaction_id: int):
        """Find transaction by id."""
        transaction_dao = PaymentTransactionModel.find_by_id(transaction_id)

        transaction = PaymentTransaction()
        transaction._dao = transaction_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return transaction
