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
"""Model to handle all operations related to invoice refund."""
from decimal import Decimal
from typing import List, Self

from attrs import define
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.schema import CheckConstraint

from ..utils.enums import RefundStatus
from ..utils.util import date_to_string
from .base_model import BaseModel
from .db import db, ma


class Refund(BaseModel):
    """This class manages all of the base data about Refunds."""

    __tablename__ = "refunds"

    __table_args__ = (
        CheckConstraint(
            "NOT(routing_slip_id IS NULL AND invoice_id IS NULL)",
            name="routing_slip_invoice" "_id_check",
        ),
    )
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
            "decision_date",
            "decision_made_by",
            "decline_reason",
            "details",
            "gl_posted",
            "gl_error",
            "invoice_id",
            "notification_email",
            "reason",
            "refund_method",
            "requested_by",
            "requested_date",
            "routing_slip_id",
            "staff_comment",
            "status",
            "type",
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, index=True)
    invoice_id = db.Column(db.Integer, ForeignKey("invoices.id"), nullable=True)
    routing_slip_id = db.Column(db.Integer, ForeignKey("routing_slips.id"), nullable=True)
    requested_date = db.Column(db.DateTime)
    reason = db.Column(db.String(250))
    requested_by = db.Column(db.String(50))
    decision_made_by = db.Column(db.String(50))
    decision_date = db.Column(db.DateTime)
    decline_reason = db.Column(db.String(), nullable=True)
    details = db.Column(JSONB)
    notification_email = db.Column(db.String(100), nullable=True)
    refund_method = db.Column(db.String(25), nullable=True)
    staff_comment = db.Column(db.String(), nullable=True)
    status = db.Column(db.String(25), nullable=False, index=True)
    type = db.Column(db.String(25), nullable=False, index=True)
    # These two fields below are used for direct pay credit card refunds.
    gl_posted = db.Column(db.DateTime, nullable=True)
    gl_error = db.Column(db.String(250), nullable=True)

    @classmethod
    def find_latest_by_invoice_id(
        cls, invoice_id: int, statuses=(RefundStatus.APPROVAL_NOT_REQUIRED.value, RefundStatus.APPROVED.value)
    ) -> Self:
        """Return a refund by invoice id."""
        return (
            cls.query.filter(cls.invoice_id == invoice_id, cls.status.in_(statuses))
            .order_by(cls.requested_date.desc())
            .one_or_none()
        )

    @classmethod
    def find_by_invoice_and_refund_id(cls, invoice_id: int, refund_id: int) -> Self:
        """Return a refund by invoice id."""
        return cls.query.filter(cls.invoice_id == invoice_id, cls.id == refund_id).one_or_none()

    @classmethod
    def find_by_routing_slip_id(
        cls, routing_slip_id: int, statuses=(RefundStatus.APPROVAL_NOT_REQUIRED.value, RefundStatus.APPROVED.value)
    ) -> Self:
        """Return a refund by invoice id."""
        return cls.query.filter(cls.routing_slip_id == routing_slip_id, cls.status.in_(statuses)).one_or_none()


class RefundSchema(ma.SQLAlchemyAutoSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Refund."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Refund
        load_instance = True


@define
class PartialRefundLineDTO:  # pylint: disable=too-few-public-methods
    """Schema used to serialize refund partial lines."""

    payment_line_item_id: int
    statutory_fee_amount: Decimal
    future_effective_fee_amount: Decimal
    priority_fee_amount: Decimal
    service_fee_amount: Decimal

    @classmethod
    def from_row(cls, row: dict):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html
        """
        return cls(
            payment_line_item_id=row.get("payment_line_item_id"),
            statutory_fee_amount=row.get("statutory_fee_amount"),
            future_effective_fee_amount=row.get("future_effective_fee_amount"),
            priority_fee_amount=row.get("priority_fee_amount"),
            service_fee_amount=row.get("service_fee_amount"),
        )


@define
class RefundDTO:  # pylint: disable=too-few-public-methods, too-many-instance-attributes
    """Schema used to serialize refunds."""

    invoice_id: int
    refund_id: int
    refund_status: str
    refund_type: str
    refund_method: str
    notification_email: str
    refund_reason: str
    staff_comment: str
    requested_by: str
    requested_date: str
    decline_reason: str
    decision_by: str
    decision_date: str
    refund_amount: Decimal
    transaction_amount: Decimal
    payment_method: str
    partial_refund_lines: List[PartialRefundLineDTO]

    @classmethod
    def from_row(  # pylint: disable=too-many-arguments
        cls, row, invoice_total: Decimal, payment_method: str, partial_refund_lines=None, refund_total: Decimal = None
    ):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html

        """
        return cls(
            invoice_id=row.invoice_id,
            refund_id=row.id,
            refund_status=row.status,
            refund_type=row.type,
            refund_method=row.refund_method,
            notification_email=row.notification_email,
            refund_reason=row.reason,
            requested_by=row.requested_by,
            requested_date=date_to_string(getattr(row, "requested_date", None)),
            decline_reason=row.decline_reason,
            decision_by=getattr(row, "decision_made_by", None),
            decision_date=date_to_string(getattr(row, "decision_date", None)),
            refund_amount=refund_total,
            transaction_amount=invoice_total,
            payment_method=payment_method,
            staff_comment=row.staff_comment,
            partial_refund_lines=partial_refund_lines or [],
        )
