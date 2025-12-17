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
"""Model that is populated from feedback files."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Self

from attrs import define
from sqlalchemy import ForeignKey, func

from .base_model import BaseModel
from .db import db


# NOTE THIS IS SPECIFIC ONLY FOR PAD / ONLINE BANKING CREDIT MEMOS.
# This can also be seen in the ar_applied_receivables table in the CAS datawarehouse.
class AppliedCredits(BaseModel):
    """This class manages the mapping from cfs account credit memos to invoices."""

    __tablename__ = "applied_credits"
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
            "account_id",
            "amount_applied",
            "application_id",
            "cfs_account",
            "cfs_identifier",
            "created_on",
            "credit_id",
            "invoice_amount",
            "invoice_number",
            "invoice_id",
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    account_id = db.Column(db.Integer, ForeignKey("payment_accounts.id"), nullable=True, index=True)
    amount_applied = db.Column(db.Numeric, nullable=False)
    # External application_id that comes straight from the CSV, looks like an identifier in an external system.
    application_id = db.Column(db.Integer, nullable=True, index=True)
    cfs_account = db.Column(db.String(50), nullable=False, index=True)
    cfs_identifier = db.Column(db.String(50), nullable=False, index=True)
    created_on = db.Column(
        "created_on",
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(tz=UTC),
    )
    credit_id = db.Column(db.Integer, ForeignKey("credits.id"), nullable=True, index=True)
    invoice_amount = db.Column(db.Numeric, nullable=False)
    invoice_number = db.Column(db.String(50), nullable=False)
    # We don't know the exact invoice id for PAD since it's rolled up. For ONLINE BANKING there is only one invoice.
    invoice_id = db.Column(db.Integer, ForeignKey("invoices.id"), nullable=False, index=True)

    @classmethod
    def credit_for_invoice_number(cls, invoice_number: str):
        """Return the credit associated with the invoice number."""
        return (
            cls.query.with_entities(func.sum(AppliedCredits.amount_applied).label("credit_invoice_total"))
            .filter_by(invoice_number=invoice_number)
            .scalar()
        )

    @classmethod
    def find_by_application_id(cls, application_id: int):
        """Return the credit associated with the application id."""
        return cls.query.filter_by(application_id=application_id).first()

    @classmethod
    def get_applied_credits_for_invoice(cls, invoice_id: int) -> list[Self]:
        """Get all applied credits for a specific invoice."""
        return cls.query.filter_by(invoice_id=invoice_id).all()


@define
class AppliedCreditsSearchModel:
    """Applied Credits Search Model."""

    id: int
    amount_applied: Decimal
    cfs_identifier: str
    created_on: datetime
    credit_id: int
    invoice_amount: Decimal
    invoice_number: str
    invoice_id: int

    @classmethod
    def from_row(cls, row: AppliedCredits):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html
        """
        return cls(
            id=row.id,
            amount_applied=row.amount_applied,
            cfs_identifier=row.cfs_identifier,
            created_on=row.created_on,
            credit_id=row.credit_id,
            invoice_amount=row.invoice_amount,
            invoice_number=row.invoice_number,
            invoice_id=row.invoice_id,
        )

    @classmethod
    def to_schema(cls, lines: list[AppliedCredits]):
        """Return list of schemas."""
        return [cls.from_row(line) for line in lines]
