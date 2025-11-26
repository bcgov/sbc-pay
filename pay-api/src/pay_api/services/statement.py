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

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from flask import current_app
from sqlalchemy import Integer, and_, case, cast, distinct, exists, func, literal, literal_column, select
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER
from sqlalchemy.sql.functions import coalesce

from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTCreditInvoiceLink as EFTCreditInvoiceLinkModel
from pay_api.models import EFTShortnameLinks as EFTShortnameLinksModel
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Statement as StatementModel
from pay_api.models import StatementInvoices as StatementInvoicesModel
from pay_api.models import StatementSchema as StatementModelSchema
from pay_api.models import StatementSettings as StatementSettingsModel
from pay_api.models import db
from pay_api.services.activity_log_publisher import ActivityLogPublisher
from pay_api.utils.constants import DT_SHORT_FORMAT
from pay_api.utils.dataclasses import StatementIntervalChangeEvent
from pay_api.utils.enums import (
    ContentType,
    EFTFileLineType,
    EFTProcessStatus,
    EFTShortnameStatus,
    InvoiceStatus,
    NotificationStatus,
    PaymentMethod,
    QueueSources,
    StatementFrequency,
    StatementTemplate,
)
from pay_api.utils.util import get_first_and_last_of_frequency, get_local_time

from .invoice import Invoice
from .invoice_search import InvoiceSearch
from .payment import PaymentReportInput


class Statement:  # pylint:disable=too-many-public-methods
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

    @classmethod
    def calculate_due_date(cls, target_date: datetime | None) -> str:
        """Calculate the due date for the statement."""
        if target_date:
            return (target_date + relativedelta(months=1, hours=8)).isoformat()
        return None

    @staticmethod
    def get_statement_owing_query():
        """Get statement query used for amount owing."""
        return (
            db.session.query(
                StatementInvoicesModel.statement_id,
                func.sum(InvoiceModel.total - InvoiceModel.paid).label("amount_owing"),
            )
            .join(
                StatementInvoicesModel,
                StatementInvoicesModel.invoice_id == InvoiceModel.id,
            )
            .filter(
                InvoiceModel.invoice_status_code.in_(
                    [
                        InvoiceStatus.PARTIAL.value,
                        InvoiceStatus.APPROVED.value,
                        InvoiceStatus.OVERDUE.value,
                    ]
                )
            )
            .group_by(StatementInvoicesModel.statement_id)
        )

    @staticmethod
    def get_statement_total(statement_id: int):
        """Get statement query used for statement total."""
        result = (
            db.session.query(
                func.sum(InvoiceModel.total - coalesce(InvoiceModel.refund, 0)).label("statement_total"),
            )
            .join(
                StatementInvoicesModel,
                StatementInvoicesModel.invoice_id == InvoiceModel.id,
            )
            .filter(StatementInvoicesModel.statement_id == cast(statement_id, Integer))
            .scalar()
        )
        return result or 0

    @staticmethod
    def find_by_id(statement_id: int):
        """Get statement by id and populate payment methods and amount owing."""
        owing_subquery = Statement.get_statement_owing_query().subquery()

        query = (
            db.session.query(StatementModel, owing_subquery.c.amount_owing)
            .join(PaymentAccountModel)
            .outerjoin(owing_subquery, owing_subquery.c.statement_id == StatementModel.id)
            .filter(
                and_(
                    PaymentAccountModel.id == StatementModel.payment_account_id,
                    cast(StatementModel.id, Integer) == cast(statement_id, Integer),
                )
            )
        )

        result = query.one()
        statement = result[0]
        amount_owing = result[1] if result[1] else 0
        statement.amount_owing = amount_owing
        statement.statement_total = Statement.get_statement_total(statement_id)
        return statement

    @staticmethod
    def get_account_statements(auth_account_id: str, page, limit, is_owing: bool = None, statement_id: int = None):
        """Return all active statements for an account."""
        query = (
            db.session.query(StatementModel)
            .join(PaymentAccountModel)
            .filter(
                and_(
                    PaymentAccountModel.id == StatementModel.payment_account_id,
                    PaymentAccountModel.auth_account_id == auth_account_id,
                )
            )
        )
        if is_owing:
            owing_subquery = Statement.get_statement_owing_query().subquery()
            query = query.add_columns(owing_subquery.c.amount_owing).outerjoin(
                owing_subquery, owing_subquery.c.statement_id == StatementModel.id
            )
            query = query.filter(owing_subquery.c.amount_owing > 0)
        else:
            query = query.add_columns(literal(0).label("amount_owing"))

        query = query.filter_conditionally(statement_id, StatementModel.id)

        frequency_case = case(
            (
                StatementModel.frequency == StatementFrequency.MONTHLY.value,
                literal_column("'1'"),
            ),
            (
                StatementModel.frequency == StatementFrequency.WEEKLY.value,
                literal_column("'2'"),
            ),
            (
                StatementModel.frequency == StatementFrequency.DAILY.value,
                literal_column("'3'"),
            ),
            else_=literal_column("'4'"),
        )

        query = query.order_by(StatementModel.to_date.desc(), frequency_case)
        pagination = query.paginate(per_page=limit, page=page)

        for i, (statement, amount_owing) in enumerate(pagination.items):
            statement.amount_owing = amount_owing if amount_owing else 0
            statement.statement_total = Statement.get_statement_total(statement.id)
            pagination.items[i] = statement

        return pagination.items, pagination.total

    @staticmethod
    def find_by_account_id(auth_account_id: str, page: int, limit: int, is_owing: bool = None):
        """Find statements by account id."""
        current_app.logger.debug(f"<search_purchase_history {auth_account_id}")
        statements, total = Statement.get_account_statements(auth_account_id, page, limit, is_owing)
        statements = Statement.populate_overdue_from_invoices(statements)
        statements_schema = StatementModelSchema()
        data = {
            "total": total,
            "page": page,
            "limit": limit,
            "items": statements_schema.dump(statements, many=True),
        }
        current_app.logger.debug(">statements_find_by_account_id")
        return data

    @staticmethod
    def get_statement_invoices(statement_id: int) -> list[InvoiceModel]:
        """Find statements by account id."""
        return (
            db.session.query(InvoiceModel)
            .join(
                StatementInvoicesModel,
                StatementInvoicesModel.invoice_id == InvoiceModel.id,
            )
            .filter(StatementInvoicesModel.statement_id == statement_id)
        )

    @staticmethod
    def is_payment_method_statement(
        statement: StatementModel, ordered_invoices: list[InvoiceModel], payment_method_code: str
    ) -> bool:
        """Return if the statement is for the specified payment method."""
        # Check invoice payment method for statement template
        if ordered_invoices and ordered_invoices[0].payment_method_code == payment_method_code:
            return True

        # In the event of an empty statement check statement payment methods, could be more than one on transition days
        if payment_method_code in (statement.payment_methods or ""):
            return True

        return False

    @staticmethod
    def get_invoices_owing_amount(auth_account_id: str):
        """Get invoices owing amount that have not been added as part of a statement yet."""
        return (
            db.session.query(func.sum(InvoiceModel.total - InvoiceModel.paid).label("invoices_owing"))
            .join(
                PaymentAccountModel,
                PaymentAccountModel.id == InvoiceModel.payment_account_id,
            )
            .filter(PaymentAccountModel.auth_account_id == auth_account_id)
            .filter(
                InvoiceModel.invoice_status_code.in_(
                    (
                        InvoiceStatus.SETTLEMENT_SCHEDULED.value,
                        InvoiceStatus.APPROVED.value,
                        InvoiceStatus.OVERDUE.value,
                    )
                )
            )
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value)
            .filter(~exists().where(StatementInvoicesModel.invoice_id == InvoiceModel.id))
            .group_by(InvoiceModel.payment_account_id)
        ).scalar()

    @staticmethod
    def get_previous_statement(statement: StatementModel) -> StatementModel:
        """Get the preceding statement."""
        return (
            db.session.query(StatementModel)
            .filter(
                StatementModel.to_date < statement.from_date,
                StatementModel.payment_account_id == statement.payment_account_id,
                StatementModel.id != statement.id,
            )
            .order_by(StatementModel.to_date.desc())
            .first()
        )

    @staticmethod
    def get_statement_eft_transactions(
        statement: StatementModel,
    ) -> list[EFTTransactionModel]:
        """Get a list of EFT transactions applied to statement invoices."""
        return (
            db.session.query(EFTTransactionModel)
            .join(
                EFTCreditModel,
                EFTCreditModel.eft_transaction_id == EFTTransactionModel.id,
            )
            .join(
                EFTCreditInvoiceLinkModel,
                EFTCreditInvoiceLinkModel.eft_credit_id == EFTCreditModel.id,
            )
            .join(
                StatementInvoicesModel,
                StatementInvoicesModel.invoice_id == EFTCreditInvoiceLinkModel.invoice_id,
            )
            .join(StatementModel, StatementModel.id == StatementInvoicesModel.statement_id)
            .filter(StatementModel.id == statement.id)
            .filter(EFTTransactionModel.status_code == EFTProcessStatus.COMPLETED.value)
            .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value)
            .all()
        )

    @classmethod
    def _populate_statement_summary(
        cls, statement: StatementModel, statement_invoices: list[InvoiceModel], payment_method: PaymentMethod
    ) -> dict:
        """Populate statement summary with additional information."""
        previous_statement = Statement.get_previous_statement(statement)
        previous_totals = None
        if previous_statement:
            previous_invoices = Statement.find_all_payments_and_invoices_for_statement(
                previous_statement.id, payment_method
            ).all()
            previous_items = InvoiceSearch.create_payment_report_details(purchases=previous_invoices, data=None)

            # Skip passing statement, we need the totals independent of the statement/payment date.
            previous_totals = InvoiceSearch.get_invoices_totals(previous_items.get("items", None), None)

        latest_payment_date = None
        for invoice in statement_invoices:
            if invoice.payment_date is None:
                continue
            if latest_payment_date is None or invoice.payment_date > latest_payment_date:
                latest_payment_date = invoice.payment_date

        return {
            "lastStatementTotal": previous_totals["fees"] if previous_totals else 0,
            "lastStatementPaidAmount": (previous_totals["paid"] if previous_totals else 0),
            "latestStatementPaymentDate": (
                latest_payment_date.strftime(DT_SHORT_FORMAT) if latest_payment_date else None
            ),
            "dueDate": cls.calculate_due_date(statement.to_date) if statement else None,
        }

    @staticmethod
    def _build_statement_summary_for_methods(
        statement_dao: StatementModel, statement_purchases: list[InvoiceModel]
    ) -> dict:
        """Build statement_summary for EFT and PAD without inflating locals in caller."""
        summary: dict = {}
        if Statement.is_payment_method_statement(statement_dao, statement_purchases, PaymentMethod.EFT.value):
            summary.update(Statement._populate_statement_summary(statement_dao, statement_purchases, PaymentMethod.EFT))
        if Statement.is_payment_method_statement(statement_dao, statement_purchases, PaymentMethod.PAD.value):
            pad_summary = Statement._populate_statement_summary(statement_dao, statement_purchases, PaymentMethod.PAD)
            pad_amount = pad_summary.get("lastStatementPaidAmount")
            if pad_amount:
                summary["lastPADStatementPaidAmount"] = pad_amount
        return summary

    @staticmethod
    def get_statement_report(statement_id: str, content_type: str, **kwargs):
        """Generate statement report."""
        current_app.logger.debug(f"<get_statement_report {statement_id}")
        report_name: str = "bcregistry-statements"

        statement_dao: StatementModel = Statement.find_by_id(statement_id)
        Statement.populate_overdue_from_invoices([statement_dao])

        statement_svc = Statement()
        statement_svc._dao = statement_dao  # pylint: disable=protected-access

        from_date_string: str = statement_svc.from_date.strftime(DT_SHORT_FORMAT)
        to_date_string: str = statement_svc.to_date.strftime(DT_SHORT_FORMAT)

        extension = "pdf" if content_type == ContentType.PDF.value else "csv"

        if statement_svc.frequency == StatementFrequency.DAILY.value:
            report_name = f"{report_name}-{from_date_string}.{extension}"
        else:
            report_name = f"{report_name}-{from_date_string}-to-{to_date_string}.{extension}"

        statement_purchases = Statement.find_all_payments_and_invoices_for_statement(statement_id)
        if extension == "pdf":
            statement_purchases = statement_purchases.all()
            result_items = InvoiceSearch.create_payment_report_details(purchases=statement_purchases, data=None)
        else:
            result_items = statement_purchases
        statement = statement_svc.asdict()
        statement["from_date"] = from_date_string
        statement["to_date"] = to_date_string

        report_inputs = PaymentReportInput(
            content_type=content_type,
            report_name=report_name,
            template_name=StatementTemplate.STATEMENT_REPORT.value,
            results=result_items,
        )

        summary = Statement._build_statement_summary_for_methods(statement_dao, statement_purchases)
        if summary:
            report_inputs.statement_summary = summary

        report_response = InvoiceSearch.generate_payment_report(
            report_inputs, auth=kwargs.get("auth", None), statement=statement
        )
        current_app.logger.debug(">get_statement_report")

        return report_response, report_name

    @staticmethod
    def get_summary(
        auth_account_id: str,
        statement_id: str = None,
        calculate_under_payment: bool = False,
    ):
        """Get summary for statements by account id."""
        # Used by payment jobs to get the total due amount for statements, keep in mind when modifying.
        # This is written outside of the model, because we have multiple model references that need to be included.
        # If we include these references inside of a model, it runs the risk of having circular dependencies.
        # It's easier to build out features if our models don't rely on other models.

        result = (
            db.session.query(
                func.sum(InvoiceModel.total - InvoiceModel.paid).label("total_due"),
                func.min(StatementModel.to_date).label("oldest_to_date"),
            )
            .join(
                PaymentAccountModel,
                PaymentAccountModel.id == StatementModel.payment_account_id,
            )
            .join(
                StatementInvoicesModel,
                StatementModel.id == StatementInvoicesModel.statement_id,
            )
            .filter(PaymentAccountModel.auth_account_id == auth_account_id)
            .filter(
                InvoiceModel.invoice_status_code.in_(
                    (
                        InvoiceStatus.SETTLEMENT_SCHEDULED.value,
                        InvoiceStatus.PARTIAL.value,
                        InvoiceStatus.APPROVED.value,
                        InvoiceStatus.OVERDUE.value,
                    )
                )
            )
            .filter(StatementInvoicesModel.invoice_id == InvoiceModel.id)
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value)
        )

        if statement_id:
            result = result.filter(StatementInvoicesModel.statement_id == statement_id)

        result = result.group_by(InvoiceModel.payment_account_id).one_or_none()

        total_due = float(result.total_due) if result else 0
        oldest_due_date = (
            Statement.calculate_due_date(result.oldest_to_date) if result and result.oldest_to_date else None
        )

        # Unpaid invoice amount total that are not part of a statement yet
        invoices_unpaid_amount = Statement.get_invoices_owing_amount(auth_account_id)
        short_name_links_count = EFTShortnameLinksModel.get_short_name_links_count(auth_account_id)

        return {
            "total_invoice_due": (float(invoices_unpaid_amount) if invoices_unpaid_amount else 0),
            "total_due": total_due,
            "oldest_due_date": oldest_due_date,
            "short_name_links_count": short_name_links_count,
            "is_eft_under_payment": Statement._is_eft_under_payment(auth_account_id, calculate_under_payment),
        }

    @staticmethod
    def _get_short_name_owing_balance(short_name_id: int) -> Decimal:
        """Get the total amount owing for a short name statements for all links."""
        # Pre-filter payment account ids so there is less data to work with
        accounts_query = (
            db.session.query(PaymentAccountModel.id)
            .join(
                EFTShortnameLinksModel,
                PaymentAccountModel.auth_account_id == EFTShortnameLinksModel.auth_account_id,
            )
            .filter(
                EFTShortnameLinksModel.eft_short_name_id == short_name_id,
                EFTShortnameLinksModel.status_code.in_(
                    [EFTShortnameStatus.LINKED.value, EFTShortnameStatus.PENDING.value]
                ),
            )
        )

        invoices_subquery = (
            db.session.query(
                distinct(InvoiceModel.id),
                InvoiceModel.id,
                InvoiceModel.total,
                InvoiceModel.paid,
            )
            .join(
                StatementInvoicesModel,
                StatementInvoicesModel.invoice_id == InvoiceModel.id,
            )
            .filter(
                and_(
                    InvoiceModel.payment_method_code == PaymentMethod.EFT.value,
                    InvoiceModel.invoice_status_code.in_([InvoiceStatus.APPROVED.value, InvoiceStatus.OVERDUE.value]),
                )
            )
            .filter(InvoiceModel.payment_account_id.in_(accounts_query))
            .subquery()
        )

        query = db.session.query(func.sum(invoices_subquery.c.total - invoices_subquery.c.paid))
        owing = query.scalar()
        return 0 if owing is None else owing

    @staticmethod
    def _is_eft_under_payment(auth_account_id: str, calculate_under_payment: bool):
        if not calculate_under_payment:
            return None
        if (active_link := EFTShortnameLinksModel.find_active_link_by_auth_id(auth_account_id)) is None:
            return None

        short_name_owing = Statement._get_short_name_owing_balance(active_link.eft_short_name_id)
        balance = EFTCreditModel.get_eft_credit_balance(active_link.eft_short_name_id)

        if 0 < balance < short_name_owing:
            return True
        return False

    @staticmethod
    def populate_overdue_from_invoices(statements: list[StatementModel]):
        """Populate is_overdue field for statements."""
        # Invoice status can change after a statement has been generated.
        statement_ids = select(func.unnest(cast([statements.id for statements in statements], ARRAY(INTEGER))))
        overdue_statements = (
            db.session.query(
                func.count(InvoiceModel.id).label("overdue_invoices"),  # pylint:disable=not-callable
                StatementInvoicesModel.statement_id,
            )
            .join(StatementInvoicesModel)
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.OVERDUE.value)
            .filter(StatementInvoicesModel.invoice_id == InvoiceModel.id)
            .filter(StatementInvoicesModel.statement_id.in_(statement_ids))
            .group_by(StatementInvoicesModel.statement_id)
            .all()
        )
        overdue_statements = {statement.statement_id: statement.overdue_invoices for statement in overdue_statements}
        for statement in statements:
            statement.is_overdue = overdue_statements.get(statement.id, 0) > 0
        return statements

    @staticmethod
    def determine_payment_methods(invoice_detail_tuple, pay_account, existing_statement=None) -> str:
        """Grab payment methods from invoices detail tuple."""
        payment_methods = {
            payment_method
            for _, payment_method, auth_account_id, _ in invoice_detail_tuple
            if pay_account.auth_account_id == auth_account_id
        }
        if existing_statement and not payment_methods:
            return existing_statement.payment_methods
        if not payment_methods:
            payment_methods = {pay_account.payment_method or ""}
        return ",".join(payment_methods)

    @staticmethod
    def generate_interim_statement(auth_account_id: str, new_frequency: str):
        """Generate interim statement."""
        today = get_local_time(datetime.now(tz=UTC))

        # This can happen during account creation when the default active settings do not exist yet
        # No interim statement is needed in this case
        if not (active_settings := StatementSettingsModel.find_active_settings(str(auth_account_id), today)):
            return None

        account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(auth_account_id)

        # End the current statement settings
        active_settings.to_date = today
        active_settings.save()
        statement_to = today
        statement_from, _ = get_first_and_last_of_frequency(today, active_settings.frequency)
        statement_filter = {
            "dateFilter": {
                "startDate": statement_from.strftime("%Y-%m-%d"),
                "endDate": statement_to.strftime("%Y-%m-%d"),
            },
            "authAccountIds": [account.auth_account_id],
        }

        invoice_detail_tuple = Invoice.get_invoices_and_payment_accounts_for_statements(statement_filter)
        invoice_ids = list(invoice_detail_tuple)
        payment_methods_string = Statement.determine_payment_methods(invoice_detail_tuple, account)

        # Generate interim statement
        statement = StatementModel(
            frequency=active_settings.frequency,
            statement_settings_id=active_settings.id,
            payment_account_id=account.id,
            created_on=today,
            from_date=statement_from,
            to_date=today,
            notification_status_code=(
                NotificationStatus.PENDING.value
                if account.statement_notification_enabled
                else NotificationStatus.SKIP.value
            ),
            is_interim_statement=True,
            payment_methods=payment_methods_string,
        ).save()

        statement_invoices = [
            StatementInvoicesModel(statement_id=statement.id, invoice_id=invoice.id) for invoice in invoice_ids
        ]

        db.session.bulk_save_objects(statement_invoices)

        # Create new statement settings for the transition
        latest_settings = StatementSettingsModel.find_latest_settings(str(auth_account_id))
        if latest_settings is None or latest_settings.id == active_settings.id:
            latest_settings = StatementSettingsModel()

        effective_date = today + timedelta(days=1)
        if latest_settings.frequency != new_frequency:
            ActivityLogPublisher.publish_statement_interval_change_event(
                StatementIntervalChangeEvent(
                    account_id=account.id,
                    old_frequency=latest_settings.frequency,
                    new_frequency=new_frequency,
                    effective_date=effective_date,
                    source=QueueSources.PAY_API.value,
                )
            )
        latest_settings.frequency = new_frequency
        latest_settings.payment_account_id = account.id
        latest_settings.from_date = effective_date
        latest_settings.save()

        return statement

    @staticmethod
    def find_all_payments_and_invoices_for_statement(
        statement_id: str, payment_method: PaymentMethod = None
    ) -> list[InvoiceModel]:
        """Find all payment and invoices specific to a statement."""
        query = (
            db.session.query(InvoiceModel)
            .join(StatementInvoicesModel, StatementInvoicesModel.invoice_id == InvoiceModel.id)
            .filter(StatementInvoicesModel.statement_id == cast(statement_id, Integer))
            .order_by(InvoiceModel.id.asc())
        )
        if payment_method:
            query = query.filter(InvoiceModel.payment_method_code == payment_method.value)

        return query
