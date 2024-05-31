# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Model to handle statements data."""

from datetime import datetime
import pytz
from marshmallow import fields
from sql_versioning import history_cls
from sqlalchemy import ForeignKey, and_, case, literal_column
from sqlalchemy.ext.hybrid import hybrid_property

from pay_api.utils.constants import LEGISLATIVE_TIMEZONE
from pay_api.utils.enums import StatementFrequency

from .base_model import BaseModel
from .db import db, ma
from .invoice import Invoice
from .payment_account import PaymentAccount


class Statement(BaseModel):
    """This class manages the statements related data."""

    __tablename__ = 'statements'
    # this mapper is used so that new and old versions of the service can be run simultaneously,
    # making rolling upgrades easier
    # This is used by SQLAlchemy to explicitly define which fields we're interested
    # so it doesn't freak out and say it can't map the structure if other fields are present.
    # This could occur from a failed deploy or during an upgrade.
    # The other option is to tell SQLAlchemy to ignore differences, but that is ambiguous
    # and can interfere with Alembic upgrades.
    #
    # NOTE: please keep mapper names in alpha-order, easier to track that way
    #       Exception, id is always first, _fields first
    __mapper_args__ = {
        'include_properties': [
            'id',
            'created_on',
            'frequency',
            'from_date',
            'is_interim_statement',
            'notification_date',
            'notification_status_code',
            'payment_account_id',
            'statement_settings_id',
            'to_date'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    frequency = db.Column(db.String(50), nullable=True, index=True)
    statement_settings_id = db.Column(db.Integer, ForeignKey('statement_settings.id'), nullable=True, index=True)
    payment_account_id = db.Column(db.Integer, ForeignKey('payment_accounts.id'), nullable=True, index=True)
    from_date = db.Column(db.Date, default=None, nullable=False)
    to_date = db.Column(db.Date, default=None, nullable=True)
    is_interim_statement = db.Column('is_interim_statement', db.Boolean(), nullable=False, default=False)

    created_on = db.Column(db.Date, default=None, nullable=False)
    notification_status_code = db.Column(db.String(20), ForeignKey('notification_status_codes.code'), nullable=True)
    notification_date = db.Column(db.Date, default=None, nullable=True)

    @hybrid_property
    def payment_methods(self):
        """Return all payment methods that were active during the statement period based on payment account versions."""
        payment_account = PaymentAccount.find_by_id(self.payment_account_id)
        payment_account_history_class = history_cls(PaymentAccount)
        payment_account_history = db.session.query(payment_account_history_class) \
            .join(Statement, Statement.payment_account_id == payment_account_history_class.id) \
            .filter(payment_account_history_class.id == self.payment_account_id) \
            .filter(Statement.id == self.id) \
            .order_by(payment_account_history_class.changed.asc()) \
            .all()

        # The code below combines the history rows with the current state of payment_account.
        # This is necessary because the new versioning doesn't have from and to dates, only changed.
        # It is possible to handle this through SQL using LEAD and LAG functions.
        # Since the volume of rows is low, the pythonic approach should be sufficient.
        history_ranges = [
            {
                'from_date': datetime.min.date() if idx == 0 else payment_account_history[idx - 1].changed.date(),
                'to_date': historical.changed.date(),
                'payment_method': payment_account.payment_method if idx == len(payment_account_history) - 1
                else historical.payment_method
            }
            for idx, historical in enumerate(payment_account_history)
        ]

        history_ranges.append({
            'from_date': payment_account_history[-1].changed.date() if payment_account_history else datetime.min.date(),
            'to_date': datetime.max.date(),
            'payment_method': payment_account.payment_method
        })

        payment_methods = {
            history_item['payment_method']
            for history_item in history_ranges
            if (
                history_item['from_date'] <= self.from_date <= history_item['to_date'] or
                history_item['from_date'] <= self.to_date <= history_item['to_date'] or
                self.from_date <= history_item['from_date'] <= self.to_date <= history_item['to_date']
            )
        }

        return list(payment_methods)

    @classmethod
    def find_all_statements_for_account(cls, auth_account_id: str, page, limit):
        """Return all active statements for an account."""
        query = cls.query \
            .join(PaymentAccount) \
            .filter(and_(PaymentAccount.id == cls.payment_account_id,
                         PaymentAccount.auth_account_id == auth_account_id))

        frequency_case = case(
            (
                Statement.frequency == StatementFrequency.MONTHLY.value,
                literal_column("'1'")
            ),
            (
                Statement.frequency == StatementFrequency.WEEKLY.value,
                literal_column("'2'")
            ),
            (
                Statement.frequency == StatementFrequency.DAILY.value,
                literal_column("'3'")
            ),
            else_=literal_column("'4'")
        )

        query = query.order_by(Statement.to_date.desc(), frequency_case)
        pagination = query.paginate(per_page=limit, page=page)
        return pagination.items, pagination.total

    @classmethod
    def find_all_statements_by_notification_status(cls, statuses):
        """Return all statements for a status.Used in cron jobs."""
        return cls.query \
            .filter(Statement.notification_status_code.in_(statuses)).all()

    @classmethod
    def find_all_payments_and_invoices_for_statement(cls, statement_id: str):
        """Find all payment and invoices specific to a statement."""
        # Import from here as the statement invoice already imports statement and causes circular import.
        from .statement_invoices import StatementInvoices  # pylint: disable=import-outside-toplevel

        query = db.session.query(Invoice) \
            .join(StatementInvoices, StatementInvoices.invoice_id == Invoice.id) \
            .filter(StatementInvoices.statement_id == statement_id)

        return query.all()


class StatementSchema(ma.SQLAlchemyAutoSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Statements."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Statement
        load_instance = True

    from_date = fields.Date(tzinfo=pytz.timezone(LEGISLATIVE_TIMEZONE))
    to_date = fields.Date(tzinfo=pytz.timezone(LEGISLATIVE_TIMEZONE))
    is_overdue = fields.Boolean()
    payment_methods = fields.List(fields.String())
