# Copyright © 2024 Province of British Columbia
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
from __future__ import annotations

from typing import List

import pytz
from attr import define
from dateutil.relativedelta import relativedelta
from marshmallow import fields
from sqlalchemy import ForeignKey, Integer, cast

from pay_api.utils.constants import LEGISLATIVE_TIMEZONE
from pay_api.utils.converter import Converter

from .base_model import BaseModel
from .db import db, ma
from .invoice import Invoice


class Statement(BaseModel):
    """This class manages the statements related data."""

    __tablename__ = "statements"
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
        "include_properties": [
            "id",
            "created_on",
            "frequency",
            "from_date",
            "is_interim_statement",
            "notification_date",
            "notification_status_code",
            "overdue_notification_date",
            "payment_account_id",
            "payment_methods",
            "statement_settings_id",
            "to_date",
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    frequency = db.Column(db.String(50), nullable=True, index=True)
    statement_settings_id = db.Column(db.Integer, ForeignKey("statement_settings.id"), nullable=True, index=True)
    payment_account_id = db.Column(db.Integer, ForeignKey("payment_accounts.id"), nullable=True, index=True)
    from_date = db.Column(db.Date, default=None, nullable=False)
    to_date = db.Column(db.Date, default=None, nullable=True)
    is_interim_statement = db.Column("is_interim_statement", db.Boolean(), nullable=False, default=False)
    overdue_notification_date = db.Column(db.Date, default=None, nullable=True)
    created_on = db.Column(db.Date, default=None, nullable=False)
    notification_status_code = db.Column(db.String(20), ForeignKey("notification_status_codes.code"), nullable=True)
    notification_date = db.Column(db.Date, default=None, nullable=True)
    payment_methods = db.Column(db.String(100), nullable=True)

    @classmethod
    def find_all_statements_by_notification_status(cls, statuses):
        """Return all statements for a status.Used in cron jobs."""
        return cls.query.filter(Statement.notification_status_code.in_(statuses)).all()

    @classmethod
    def find_all_payments_and_invoices_for_statement(cls, statement_id: str) -> List[Invoice]:
        """Find all payment and invoices specific to a statement."""
        # Import from here as the statement invoice already imports statement and causes circular import.
        from .statement_invoices import StatementInvoices  # pylint: disable=import-outside-toplevel

        query = (
            db.session.query(Invoice)
            .join(StatementInvoices, StatementInvoices.invoice_id == Invoice.id)
            .filter(StatementInvoices.statement_id == cast(statement_id, Integer))
            .order_by(Invoice.id.asc())
        )

        return query.all()

    @classmethod
    def find_statement_by_account(cls, payment_account_id: int, statement_id: int):
        """Return statement for a payment account."""
        return (
            cls.query.filter(Statement.payment_account_id == payment_account_id)
            .filter(Statement.id == statement_id)
            .all()
        )


class StatementSchema(ma.SQLAlchemyAutoSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Statements."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Statement
        load_instance = True

    from_date = fields.Date(tzinfo=pytz.timezone(LEGISLATIVE_TIMEZONE))
    to_date = fields.Date(tzinfo=pytz.timezone(LEGISLATIVE_TIMEZONE))
    is_overdue = fields.Boolean()
    payment_methods = fields.Method(serialize="payment_methods_to_list")
    amount_owing = fields.Float(load_default=0)
    statement_total = fields.Float(load_default=0)

    def payment_methods_to_list(self, target):
        """Convert comma separated string to list."""
        return target.payment_methods.split(",") if target.payment_methods else []


@define
class StatementDTO:  # pylint: disable=too-few-public-methods, too-many-instance-attributes
    """Schema used for Statements to be converted into dtos."""

    id: int
    is_interim_statement: bool
    frequency: str
    from_date: str
    payment_methods: str
    to_date: str

    @classmethod
    def from_row(cls, row):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html

        """
        return cls(
            id=row.id,
            frequency=row.frequency,
            from_date=(row.from_date + relativedelta(hours=8)).isoformat(),
            is_interim_statement=row.is_interim_statement,
            payment_methods=row.payment_methods,
            to_date=(row.to_date + relativedelta(hours=8)).isoformat(),
        )

    @classmethod
    def dao_to_dict(cls, statement_daos: List[Statement]) -> dict[StatementDTO]:
        """Convert from DAO to DTO dict."""
        statements_dto = [StatementDTO.from_row(statement) for statement in statement_daos]
        statements_dict = Converter().unstructure(statements_dto)
        statements_dict = [Converter().remove_nones(statement_dict) for statement_dict in statements_dict]
        return statements_dict
