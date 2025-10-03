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
"""Model to handle all operations related to Routing Slip."""

from __future__ import annotations

from datetime import datetime
from operator import and_
from typing import List

from marshmallow import fields
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from pay_api.utils.enums import PaymentMethod, RoutingSlipStatus

from .audit import Audit, AuditSchema
from .base_schema import BaseSchema
from .db import db, ma
from .invoice import InvoiceSchema
from .payment import PaymentSchema
from .payment_account import PaymentAccountSchema
from .refund import RefundSchema


class RoutingSlip(Audit):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Routing Slip."""

    __tablename__ = "routing_slips"
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
            "cas_version_suffix",
            "created_by",
            "created_name",
            "created_on",
            "id",
            "number",
            "parent_number",
            "payment_account_id",
            "refund_amount",
            "refund_status",
            "remaining_amount",
            "routing_slip_date",
            "status",
            "total_usd",
            "total",
            "updated_by",
            "updated_name",
            "updated_on",
            "contact_name",
            "street",
            "street_additional",
            "city",
            "region",
            "postal_code",
            "country",
            "delivery_instructions",
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number = db.Column(db.String(), unique=True)
    payment_account_id = db.Column(db.Integer, ForeignKey("payment_accounts.id"), nullable=True, index=True)
    status = db.Column(
        db.String(),
        ForeignKey("routing_slip_status_codes.code"),
        nullable=True,
        index=True,
    )
    total = db.Column(db.Numeric(), nullable=True, default=0)
    remaining_amount = db.Column(db.Numeric(), nullable=True, default=0)
    routing_slip_date = db.Column(db.Date, nullable=False)
    parent_number = db.Column(db.String(), ForeignKey("routing_slips.number"), nullable=True)
    refund_amount = db.Column(db.Numeric(), nullable=True, default=0)
    refund_status = db.Column(db.String(), nullable=True)
    total_usd = db.Column(db.Numeric(), nullable=True)  # Capture total usd payments if one of payments has USD payment
    # It's not possible to update a receipt's amount or number in CAS (PUT/PATCH).
    # Allows to create a new receipt in CAS for the same routing slip number.
    # Earlier versions should be adjusted to zero before increasing the cas_version_suffix.
    cas_version_suffix = db.Column(db.Integer, default=1)
    contact_name = db.Column(db.String(), nullable=True)
    street = db.Column(db.String(), nullable=True)
    street_additional = db.Column(db.String(), nullable=True)
    city = db.Column(db.String(), nullable=True)
    region = db.Column(db.String(), nullable=True)
    postal_code = db.Column(db.String(), nullable=True)
    country = db.Column(db.String(), nullable=True)
    delivery_instructions = db.Column(db.String(), nullable=True)

    payment_account = relationship(
        "PaymentAccount",
        primaryjoin="and_(RoutingSlip.payment_account_id == PaymentAccount.id)",
        foreign_keys=[payment_account_id],
        lazy="select",
        innerjoin=True,
    )
    payments = relationship(
        "Payment",
        primaryjoin="and_(RoutingSlip.payment_account_id == foreign(Payment.payment_account_id))",
        viewonly=True,
        lazy="joined",
    )

    invoices = relationship(
        "Invoice",
        primaryjoin="and_(RoutingSlip.number == foreign(Invoice.routing_slip), "
        f"Invoice.payment_method_code.in_("
        f"['{PaymentMethod.INTERNAL.value}']))",
        viewonly=True,
        lazy="joined",
    )

    refunds = relationship(
        "Refund",
        viewonly=True,
        primaryjoin=f"and_(RoutingSlip.id == Refund.routing_slip_id,"
        f"RoutingSlip.status.in_("
        f'[f"{RoutingSlipStatus.REFUND_REQUESTED.value}",'
        f'f"{RoutingSlipStatus.ACTIVE.value}",'
        f'f"{RoutingSlipStatus.REFUND_AUTHORIZED.value}",'
        f'f"{RoutingSlipStatus.REFUND_PROCESSED.value}",'
        f'f"{RoutingSlipStatus.REFUND_REJECTED.value}",'
        f'f"{RoutingSlipStatus.REFUND_AUTHORIZED.value}"]))',
        lazy="joined",
    )

    parent = relationship("RoutingSlip", remote_side=[number], lazy="select")

    def generate_cas_receipt_number(self) -> str:
        """Return a unique identifier - receipt number for CAS."""
        receipt_number: str = self.number
        if self.parent_number:
            receipt_number += "L"
        if self.cas_version_suffix > 1:
            receipt_number += f"R{self.cas_version_suffix}"
        return receipt_number

    @classmethod
    def find_by_number(cls, number: str) -> RoutingSlip:
        """Return a routing slip by number."""
        return cls.query.filter_by(number=number).one_or_none()

    @classmethod
    def find_children(cls, number: str) -> list[RoutingSlip]:
        """Return children for the routing slip."""
        return cls.query.filter_by(parent_number=number).all()

    @classmethod
    def find_by_payment_account_id(cls, payment_account_id: str) -> RoutingSlip:
        """Return a routing slip by payment account number."""
        return cls.query.filter_by(payment_account_id=payment_account_id).one_or_none()

    @classmethod
    def find_all_by_payment_account_id(cls, payment_account_id: str) -> list[RoutingSlip]:
        """Return a routing slip by payment account number."""
        return cls.query.filter_by(payment_account_id=payment_account_id).all()


class RoutingSlipSchema(AuditSchema, BaseSchema):  # pylint: disable=too-many-ancestors, too-few-public-methods
    """Main schema used to serialize the Routing Slip."""

    class Meta(BaseSchema.Meta):  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = RoutingSlip
        exclude = ["parent"]

    total = fields.Float(data_key="total")
    remaining_amount = fields.Float(data_key="remaining_amount")
    refund_amount = fields.Float(data_key="refund_amount")
    # pylint: disable=no-member
    payments = ma.Nested(PaymentSchema, many=True, data_key="payments")
    payment_account = ma.Nested(PaymentAccountSchema, many=False, data_key="payment_account")
    refunds = ma.Nested(RefundSchema, many=True, data_key="refunds")
    invoices = ma.Nested(InvoiceSchema, many=True, data_key="invoices", exclude=["_links"])
    status = fields.String(data_key="status")
    refund_status = fields.String(data_key="refund_status")
    parent_number = fields.String(data_key="parent_number")
    total_usd = fields.Float(data_key="total_usd")
    contact_name = fields.String(data_key="contact_name")
    street = fields.String(data_key="street")
    street_additional = fields.String(data_key="street_additional")
    city = fields.String(data_key="city")
    region = fields.String(data_key="region")
    postal_code = fields.String(data_key="postal_code")
    country = fields.String(data_key="country")
    delivery_instructions = fields.String(data_key="delivery_instructions")
