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

import pytz
from marshmallow import fields
from sqlalchemy import ForeignKey, and_, case, literal_column

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

    created_on = db.Column(db.Date, default=None, nullable=False)
    notification_status_code = db.Column(db.String(20), ForeignKey('notification_status_codes.code'), nullable=True)
    notification_date = db.Column(db.Date, default=None, nullable=True)

    @classmethod
    def find_all_statements_for_account(cls, auth_account_id: str, page, limit):
        """Return all active statements for an account."""
        query = cls.query \
            .join(PaymentAccount) \
            .filter(and_(PaymentAccount.id == cls.payment_account_id,
                         PaymentAccount.auth_account_id == auth_account_id))

        frequency_case = case(
            [
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
                )
            ],
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


class StatementSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Statements."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Statement

    from_date = fields.Date(tzinfo=pytz.timezone(LEGISLATIVE_TIMEZONE))
    to_date = fields.Date(tzinfo=pytz.timezone(LEGISLATIVE_TIMEZONE))
    is_overdue = fields.Boolean()
