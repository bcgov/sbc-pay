# Copyright © 2024 Province of British Columbia
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
from datetime import date, datetime, timedelta, timezone
from typing import List

from flask import current_app
from sqlalchemy import Integer, and_, case, cast, exists, func, literal, literal_column

from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTCreditInvoiceLink as EFTCreditInvoiceLinkModel
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Statement as StatementModel
from pay_api.models import StatementInvoices as StatementInvoicesModel
from pay_api.models import StatementSchema as StatementModelSchema
from pay_api.models import StatementSettings as StatementSettingsModel
from pay_api.models import db
from pay_api.utils.constants import DT_SHORT_FORMAT
from pay_api.utils.enums import (
    ContentType, EFTFileLineType, EFTProcessStatus, InvoiceStatus, NotificationStatus, PaymentMethod,
    StatementFrequency, StatementTemplate)
from pay_api.utils.util import get_first_and_last_of_frequency, get_local_time

from .payment import Payment as PaymentService
from .payment import PaymentReportInput


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

    @staticmethod
    def get_statement_owing_query():
        """Get statement query used for amount owing."""
        return (
            db.session.query(
                StatementInvoicesModel.statement_id,
                func.sum(InvoiceModel.total - InvoiceModel.paid).label('amount_owing'))
            .join(StatementInvoicesModel, StatementInvoicesModel.invoice_id == InvoiceModel.id)
            .filter(InvoiceModel.invoice_status_code.in_([
                InvoiceStatus.PARTIAL.value,
                InvoiceStatus.APPROVED.value,
                InvoiceStatus.OVERDUE.value])
            )
            .group_by(StatementInvoicesModel.statement_id)
        )

    @staticmethod
    def find_by_id(statement_id: int):
        """Get statement by id and populate payment methods and amount owing."""
        owing_subquery = Statement.get_statement_owing_query().subquery()

        query = (db.session.query(StatementModel,
                                  owing_subquery.c.amount_owing
                                  )
                 .join(PaymentAccountModel)
                 .outerjoin(owing_subquery, owing_subquery.c.statement_id == StatementModel.id)
                 .filter(and_(PaymentAccountModel.id == StatementModel.payment_account_id,
                              cast(StatementModel.id, Integer) == cast(statement_id, Integer))))

        result = query.one()
        amount_owing = result[1] if result[1] else 0
        result[0].amount_owing = amount_owing
        return result[0]

    @staticmethod
    def get_account_statements(auth_account_id: str, page, limit, is_owing: bool = None):
        """Return all active statements for an account."""
        query = (db.session.query(StatementModel).join(PaymentAccountModel)
                 .filter(and_(PaymentAccountModel.id == StatementModel.payment_account_id,
                         PaymentAccountModel.auth_account_id == auth_account_id)))
        if is_owing:
            owing_subquery = Statement.get_statement_owing_query().subquery()
            query = query.add_columns(owing_subquery.c.amount_owing).outerjoin(
                owing_subquery,
                owing_subquery.c.statement_id == StatementModel.id
            )
            query = query.filter(owing_subquery.c.amount_owing > 0)
        else:
            query = query.add_columns(literal(0).label('amount_owing'))

        frequency_case = case(
            (
                StatementModel.frequency == StatementFrequency.MONTHLY.value,
                literal_column("'1'")
            ),
            (
                StatementModel.frequency == StatementFrequency.WEEKLY.value,
                literal_column("'2'")
            ),
            (
                StatementModel.frequency == StatementFrequency.DAILY.value,
                literal_column("'3'")
            ),
            else_=literal_column("'4'")
        )

        query = query.order_by(StatementModel.to_date.desc(), frequency_case)
        pagination = query.paginate(per_page=limit, page=page)

        for i, (statement, amount_owing) in enumerate(pagination.items):
            statement.amount_owing = amount_owing if amount_owing else 0
            pagination.items[i] = statement

        return pagination.items, pagination.total

    @staticmethod
    def find_by_account_id(auth_account_id: str, page: int, limit: int, is_owing: bool = None):
        """Find statements by account id."""
        current_app.logger.debug(f'<search_purchase_history {auth_account_id}')
        statements, total = Statement.get_account_statements(auth_account_id, page, limit, is_owing)
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
    def get_statement_invoices(statement_id: int) -> List[InvoiceModel]:
        """Find statements by account id."""
        return (db.session.query(InvoiceModel)
                .join(StatementInvoicesModel, StatementInvoicesModel.invoice_id == InvoiceModel.id)
                .filter(StatementInvoicesModel.statement_id == statement_id))

    @staticmethod
    def get_statement_template(statement: StatementModel, ordered_invoices: List[InvoiceModel]) -> str:
        """Return the statement template name."""
        # Check invoice payment method for statement template
        if ordered_invoices and ordered_invoices[0].payment_method_code == PaymentMethod.EFT.value:
            return StatementTemplate.EFT_STATEMENT.value

        # In the event of an empty statement check statement payment methods, could be more than one on transition days
        if PaymentMethod.EFT.value in statement.payment_methods:
            return StatementTemplate.EFT_STATEMENT.value

        return StatementTemplate.STATEMENT_REPORT.value

    @staticmethod
    def get_invoices_owing_amount(auth_account_id: str):
        """Get invoices owing amount that have not been added as part of a statement yet."""
        return (db.session.query(func.sum(InvoiceModel.total - InvoiceModel.paid).label('invoices_owing'))
                .join(PaymentAccountModel, PaymentAccountModel.id == InvoiceModel.payment_account_id)
                .filter(PaymentAccountModel.auth_account_id == auth_account_id)
                .filter(InvoiceModel.invoice_status_code.in_((InvoiceStatus.SETTLEMENT_SCHEDULED.value,
                                                              InvoiceStatus.PARTIAL.value,
                                                              InvoiceStatus.CREATED.value,
                                                              InvoiceStatus.OVERDUE.value)))
                .filter(~exists()
                        .where(StatementInvoicesModel.invoice_id == InvoiceModel.id))
                .group_by(InvoiceModel.payment_account_id)
                ).scalar()

    @staticmethod
    def get_previous_statement(statement: StatementModel) -> StatementModel:
        """Get the preceding statement."""
        return db.session.query(StatementModel)\
            .filter(StatementModel.to_date < statement.from_date,
                    StatementModel.payment_account_id == statement.payment_account_id,
                    StatementModel.id != statement.id)\
            .order_by(StatementModel.to_date.desc()).first()

    @staticmethod
    def get_statement_eft_transactions(statement: StatementModel) -> List[EFTTransactionModel]:
        """Get a list of EFT transactions applied to statement invoices."""
        return db.session.query(EFTTransactionModel) \
            .join(EFTCreditModel, EFTCreditModel.eft_transaction_id == EFTTransactionModel.id) \
            .join(EFTCreditInvoiceLinkModel, EFTCreditInvoiceLinkModel.eft_credit_id == EFTCreditModel.id) \
            .join(StatementInvoicesModel, StatementInvoicesModel.invoice_id == EFTCreditInvoiceLinkModel.invoice_id) \
            .join(StatementModel, StatementModel.id == StatementInvoicesModel.statement_id) \
            .filter(StatementModel.id == statement.id) \
            .filter(EFTTransactionModel.status_code == EFTProcessStatus.COMPLETED.value) \
            .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value).all()

    @classmethod
    def _populate_statement_summary(cls, statement: StatementModel, statement_invoices: List[InvoiceModel]) -> dict:
        """Populate statement summary with additional information."""
        previous_statement: StatementModel = Statement.get_previous_statement(statement)
        previous_totals = None
        if previous_statement:
            previous_invoices = StatementModel.find_all_payments_and_invoices_for_statement(previous_statement.id)
            previous_items: dict = PaymentService.create_payment_report_details(purchases=previous_invoices, data=None)
            previous_totals = PaymentService.get_invoices_totals(previous_items.get('items', None))

        latest_payment_date = None
        for invoice in statement_invoices:
            if latest_payment_date is None or invoice.payment_date > latest_payment_date:
                latest_payment_date = invoice.payment_date

        return {
            'lastStatementTotal': previous_totals['fees'] if previous_totals else 0,
            'lastStatementPaidAmount': previous_totals['paid'] if previous_totals else 0,
            'latestStatementPaymentDate': latest_payment_date.strftime(DT_SHORT_FORMAT) if latest_payment_date else None
        }

    @staticmethod
    def get_statement_report(statement_id: str, content_type: str, **kwargs):
        """Generate statement report."""
        current_app.logger.debug(f'<get_statement_report {statement_id}')
        report_name: str = 'bcregistry-statements'

        statement_dao: StatementModel = Statement.find_by_id(statement_id)
        Statement.populate_overdue_from_invoices([statement_dao])

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

        template_name = Statement.get_statement_template(statement_dao, statement_purchases)
        report_inputs = PaymentReportInput(content_type=content_type,
                                           report_name=report_name,
                                           template_name=template_name,
                                           results=result_items)

        if template_name == StatementTemplate.EFT_STATEMENT.value:
            report_inputs.statement_summary = Statement._populate_statement_summary(statement_dao,
                                                                                    statement_purchases)
            report_inputs.eft_transactions = Statement.get_statement_eft_transactions(statement_dao)

        report_response = PaymentService.generate_payment_report(report_inputs,
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
                                                          InvoiceStatus.APPROVED.value,
                                                          InvoiceStatus.OVERDUE.value))) \
            .filter(StatementInvoicesModel.invoice_id == InvoiceModel.id)

        if statement_id:
            result = result.filter(StatementInvoicesModel.statement_id == statement_id)

        result = result.group_by(InvoiceModel.payment_account_id) \
            .one_or_none()

        total_due = float(result.total_due) if result else 0
        oldest_overdue_date = result.oldest_overdue_date.strftime('%Y-%m-%d') \
            if result and result.oldest_overdue_date else None

        # Unpaid invoice amount total that are not part of a statement yet
        invoices_unpaid_amount = Statement.get_invoices_owing_amount(auth_account_id)

        return {
            'total_invoice_due': float(invoices_unpaid_amount) if invoices_unpaid_amount else 0,
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
    def get_payment_methods_from_details(invoice_detail_tuple, pay_account) -> str:
        """Grab payment methods from invoices detail tuple."""
        payment_methods = {payment_method for _, payment_method, _,
                           auth_account_id in invoice_detail_tuple if pay_account.auth_account_id == auth_account_id}
        if not payment_methods:
            payment_methods = {pay_account.payment_method}
        return ','.join(payment_methods)

    @staticmethod
    def generate_interim_statement(auth_account_id: str, new_frequency: str):
        """Generate interim statement."""
        today = get_local_time(datetime.now(tz=timezone.utc))

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

        invoice_detail_tuple = PaymentModel.get_invoices_and_payment_accounts_for_statements(statement_filter)
        invoice_ids = list(invoice_detail_tuple)
        payment_methods_string = Statement.get_payment_methods_from_details(invoice_detail_tuple, account)

        # Generate interim statement
        statement = StatementModel(
            frequency=active_settings.frequency,
            statement_settings_id=active_settings.id,
            payment_account_id=account.id,
            created_on=today,
            from_date=statement_from,
            to_date=today,
            notification_status_code=NotificationStatus.PENDING.value
            if account.statement_notification_enabled else NotificationStatus.SKIP.value,
            is_interim_statement=True,
            payment_methods=payment_methods_string
        ).save()

        statement_invoices = [StatementInvoicesModel(
            statement_id=statement.id,
            invoice_id=invoice.id
        ) for invoice in invoice_ids]

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
