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
from datetime import date, datetime, timedelta
from typing import List

from flask import current_app
from sqlalchemy import func

from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Statement as StatementModel
from pay_api.models import StatementInvoices as StatementInvoicesModel
from pay_api.models import StatementSchema as StatementModelSchema
from pay_api.models import StatementSettings as StatementSettingsModel
from pay_api.models import db
from pay_api.utils.constants import DT_SHORT_FORMAT
from pay_api.utils.enums import ContentType, InvoiceStatus, NotificationStatus, StatementFrequency
from pay_api.utils.util import get_first_and_last_of_frequency, get_local_formatted_date, get_local_time

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
        statements = Statement.populate_overdue_from_invoices(statements)
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
    def get_summary(auth_account_id: str, statement_id: str = None):
        """Get summary for statements by account id."""
        # Used by payment jobs to get the total due amount for statements, keep in mind when modifying.
        # This is written outside of the model, because we have multiple model references that need to be included.
        # If we include these references inside of a model, it runs the risk of having circular dependencies.
        # It's easier to build out features if our models don't rely on other models.
        result = db.session.query(func.sum(InvoiceModel.total - InvoiceModel.paid).label('total_due'),
                                  func.min(InvoiceModel.overdue_date).label('oldest_overdue_date')) \
            .join(PaymentAccountModel) \
            .join(StatementInvoicesModel) \
            .filter(PaymentAccountModel.auth_account_id == auth_account_id) \
            .filter(InvoiceModel.invoice_status_code.in_((InvoiceStatus.SETTLEMENT_SCHEDULED.value,
                                                          InvoiceStatus.PARTIAL.value,
                                                          InvoiceStatus.CREATED.value,
                                                          InvoiceStatus.OVERDUE.value))) \
            .filter(StatementInvoicesModel.invoice_id == InvoiceModel.id)

        if statement_id:
            result = result.filter(StatementInvoicesModel.statement_id == statement_id)

        result = result.group_by(InvoiceModel.payment_account_id) \
            .one_or_none()

        total_due = float(result.total_due) if result else 0
        oldest_overdue_date = get_local_formatted_date(result.oldest_overdue_date) \
            if result and result.oldest_overdue_date else None
        return {
            'total_due': total_due,
            'oldest_overdue_date': oldest_overdue_date
        }

    @staticmethod
    def populate_overdue_from_invoices(statements: List[StatementModel]):
        """Populate is_overdue field for statements."""
        # Invoice status can change after a statement has been generated.
        statement_ids = [statements.id for statements in statements]
        overdue_statements = db.session.query(
                func.count(InvoiceModel.id).label('overdue_invoices'),  # pylint:disable=not-callable
                StatementInvoicesModel.statement_id) \
            .join(StatementInvoicesModel) \
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.OVERDUE.value) \
            .filter(StatementInvoicesModel.invoice_id == InvoiceModel.id) \
            .filter(StatementInvoicesModel.statement_id.in_(statement_ids)) \
            .group_by(StatementInvoicesModel.statement_id) \
            .all()
        overdue_statements = {statement.statement_id: statement.overdue_invoices for statement in overdue_statements}
        for statement in statements:
            statement.is_overdue = overdue_statements.get(statement.id, 0) > 0
        return statements

    @staticmethod
    def generate_interim_statement(auth_account_id: str, new_frequency: str):
        """Generate interim statement."""
        today = get_local_time(datetime.today())

        # This can happen during account creation when the default active settings do not exist yet
        # No interim statement is needed in this case
        if not (active_settings := StatementSettingsModel.find_active_settings(str(auth_account_id), today)):
            return None

        account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)

        # End the current statement settings
        active_settings.to_date = today
        active_settings.save()
        statement_from, statement_to = get_first_and_last_of_frequency(today, active_settings.frequency)
        statement_filter = {
            'dateFilter': {
                'startDate': statement_from.strftime('%Y-%m-%d'),
                'endDate': statement_to.strftime('%Y-%m-%d')
            },
            'authAccountIds': [account.auth_account_id]
        }

        # Generate interim statement
        statement = StatementModel(
            frequency=active_settings.frequency,
            statement_settings_id=active_settings.id,
            payment_account_id=account.id,
            created_on=today,
            from_date=statement_from,
            to_date=today,
            notification_status_code=NotificationStatus.PENDING.value
            if account.statement_notification_enabled else NotificationStatus.SKIP.value
        ).save()

        invoices_and_auth_ids = PaymentModel.get_invoices_for_statements(statement_filter)
        invoices = list(invoices_and_auth_ids)

        statement_invoices = [StatementInvoicesModel(
            statement_id=statement.id,
            invoice_id=invoice.id
        ) for invoice in invoices]

        db.session.bulk_save_objects(statement_invoices)

        # Create new statement settings for the transition
        latest_settings = StatementSettingsModel.find_latest_settings(str(auth_account_id))
        if latest_settings is None or latest_settings.id == active_settings.id:
            latest_settings = StatementSettingsModel()

        latest_settings.frequency = new_frequency
        latest_settings.payment_account_id = account.id
        latest_settings.from_date = today + timedelta(days=1)
        latest_settings.save()

        return statement
