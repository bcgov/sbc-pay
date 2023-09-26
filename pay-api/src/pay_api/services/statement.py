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
"""Service class to control all the operations related to statements."""
from datetime import date, datetime

from flask import current_app
from sqlalchemy import func

from pay_api.models import db
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Statement as StatementModel
from pay_api.models import StatementInvoices as StatementInvoicesModel
from pay_api.models import StatementSchema as StatementModelSchema
from pay_api.utils.enums import ContentType, InvoiceStatus, StatementFrequency
from pay_api.utils.constants import DT_SHORT_FORMAT
from pay_api.utils.util import get_local_formatted_date
from .payment import Payment as PaymentService


class Statement:  # pylint:disable=too-many-instance-attributes
    """Service to manage statement related operations."""

    def __init__(self):
        """Return a Statement Service Object."""
        self.__dao = None
        self._id: int = None
        self._frequency = None
        self._from_date = None
        self._to_date = None
        self._payment_account_id = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = StatementModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.frequency: str = self._dao.frequency
        self.from_date: datetime = self._dao.from_date
        self.to_date: datetime = self._dao.to_date
        self.payment_account_id: int = self._dao.payment_account_id

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
    def payment_account_id(self):
        """Return the payment_account_id."""
        return self._payment_account_id

    @payment_account_id.setter
    def payment_account_id(self, value: str):
        """Set the account_id."""
        self._payment_account_id = value
        self._dao.payment_account_id = value

    @property
    def frequency(self):
        """Return the frequency."""
        return self._frequency

    @frequency.setter
    def frequency(self, value: int):
        """Set the frequency."""
        self._frequency = value
        self._dao.frequency = value

    @property
    def to_date(self):
        """Return the to_date of the statement."""
        return self._to_date

    @to_date.setter
    def to_date(self, value: date):
        """Set the to_date for the statement."""
        self._to_date = value
        self._dao.to_date = value

    @property
    def from_date(self):
        """Return the from_date of the statement."""
        return self._from_date

    @from_date.setter
    def from_date(self, value: date):
        """Set the from for the statement."""
        self._from_date = value
        self._dao.from_date = value

    def asdict(self):
        """Return the invoice as a python dict."""
        statement_schema = StatementModelSchema()
        d = statement_schema.dump(self._dao)
        return d

    @staticmethod
    def find_by_account_id(auth_account_id: str, page: int, limit: int):
        """Find statements by account id."""
        current_app.logger.debug(f'<search_purchase_history {auth_account_id}')
        statements, total = StatementModel.find_all_statements_for_account(auth_account_id, page, limit)

        statements_schema = StatementModelSchema()
        data = {
            'total': total,
            'page': page,
            'limit': limit,
            'items': statements_schema.dump(statements, many=True)
        }
        current_app.logger.debug('>statements_find_by_account_id')
        return data

    @staticmethod
    def get_statement_report(statement_id: str, content_type: str, template_name='statement_report', **kwargs):
        """Generate statement report."""
        current_app.logger.debug(f'<get_statement_report {statement_id}')
        report_name: str = 'bcregistry-statements'

        statement_dao: StatementModel = StatementModel.find_by_id(statement_id)

        statement_svc = Statement()
        statement_svc._dao = statement_dao  # pylint: disable=protected-access

        from_date_string: str = statement_svc.from_date.strftime(DT_SHORT_FORMAT)
        to_date_string: str = statement_svc.to_date.strftime(DT_SHORT_FORMAT)

        extension: str = 'pdf' if content_type == ContentType.PDF.value else 'csv'

        if statement_svc.frequency == StatementFrequency.DAILY.value:
            report_name = f'{report_name}-{from_date_string}.{extension}'
        else:
            report_name = f'{report_name}-{from_date_string}-to-{to_date_string}.{extension}'

        statement_purchases = StatementModel.find_all_payments_and_invoices_for_statement(statement_id)

        result_items: dict = PaymentService.create_payment_report_details(purchases=statement_purchases, data=None)
        statement = statement_svc.asdict()
        statement['from_date'] = from_date_string
        statement['to_date'] = to_date_string

        report_response = PaymentService.generate_payment_report(content_type, report_name, result_items,
                                                                 template_name,
                                                                 auth=kwargs.get('auth', None),
                                                                 statement=statement)
        current_app.logger.debug('>get_statement_report')

        return report_response, report_name

    @staticmethod
    def get_summary(auth_account_id: str):
        """Get summary for statements by account id."""
        # This is written outside of the model, because we have multiple model references that need to be included.
        # If we include these references inside of a model, it runs the risk of having circular dependencies.
        # It's easier to build out features if our models don't rely on other models.
        result = db.session.query(func.sum(InvoiceModel.total - InvoiceModel.paid).label('total_due'),
                                  func.min(InvoiceModel.overdue_date).label('oldest_due_date')) \
            .join(PaymentAccountModel) \
            .join(StatementInvoicesModel) \
            .filter(PaymentAccountModel.auth_account_id == auth_account_id) \
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.OVERDUE.value) \
            .filter(StatementInvoicesModel.invoice_id == InvoiceModel.id) \
            .group_by(InvoiceModel.payment_account_id) \
            .one_or_none()

        total_due = float(result.total_due) if result else 0
        oldest_due_date = get_local_formatted_date(result.oldest_due_date) if result else None
        return {
            'total_due': total_due,
            'oldest_due_date': oldest_due_date
        }
