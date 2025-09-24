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
"""Model to handle all operations related to Payment Line Item partial refunds."""

from decimal import Decimal
from typing import Self

from attrs import define
from sql_versioning import Versioned
from sqlalchemy import ForeignKey

from ..utils.enums import RefundsPartialType  # noqa: TID252
from .audit import Audit
from .base_model import BaseModel
from .db import db


class RefundsPartial(Audit, Versioned, BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages the data for payment line item partial refunds."""

    __tablename__ = "refunds_partial"
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
            "created_by",
            "created_on",
            "created_name",
            "gl_error",
            "gl_posted",
            "invoice_id",
            "is_credit",
            "payment_line_item_id",
            "refund_amount",
            "refund_type",
            "status",
            "updated_by",
            "updated_on",
            "updated_name",
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_line_item_id = db.Column(db.Integer, ForeignKey("payment_line_items.id"), nullable=False, index=True)
    refund_amount = db.Column(db.Numeric(19, 2), nullable=False)
    refund_type = db.Column(db.String(50), nullable=True)
    gl_posted = db.Column(db.DateTime, nullable=True)
    invoice_id = db.Column(db.Integer, ForeignKey("invoices.id"), nullable=True)
    is_credit = db.Column(db.Boolean, nullable=False, server_default="f", default=False)
    status = db.Column(db.String(20), nullable=True)
    gl_error = db.Column(db.String(250), nullable=True)

    @classmethod
    def get_partial_refunds_for_invoice(cls, invoice_id: int) -> list[Self]:
        """Get all partial refunds for a specific invoice."""
        return cls.query.filter_by(invoice_id=invoice_id).all()


@define
class RefundPartialLine:
    """Used to feed for partial refunds."""

    payment_line_item_id: int
    refund_amount: Decimal
    refund_type: RefundsPartialType

    @classmethod
    def from_row(cls, row: RefundsPartial):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html
        """
        return cls(
            payment_line_item_id=row.payment_line_item_id, refund_amount=row.refund_amount, refund_type=row.refund_type
        )


@define
class RefundPartialSearch:
    """Used to search for partial refunds."""

    id: int
    payment_line_item_id: int
    refund_type: str
    refund_amount: Decimal
    created_by: str
    created_name: str
    created_on: str
    is_credit: bool

    @classmethod
    def from_row(cls, row: RefundsPartial):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html
        """
        return cls(
            id=row.id,
            payment_line_item_id=row.payment_line_item_id,
            refund_type=row.refund_type,
            refund_amount=row.refund_amount,
            created_by=row.created_by,
            created_name=row.created_name,
            created_on=str(row.created_on) if row.created_on else "",
            is_credit=row.is_credit,
        )
