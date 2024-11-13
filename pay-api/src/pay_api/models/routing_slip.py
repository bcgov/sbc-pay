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
from typing import Dict, List

import pytz
from flask import current_app
from marshmallow import fields
from sqlalchemy import ForeignKey, Numeric, cast, func
from sqlalchemy.orm import contains_eager, lazyload, load_only, relationship

from pay_api.utils.constants import DT_SHORT_FORMAT
from pay_api.utils.enums import PaymentMethod, RoutingSlipStatus
from pay_api.utils.util import get_str_by_path

from .audit import Audit, AuditSchema
from .base_schema import BaseSchema
from .db import db, ma
from .invoice import Invoice, InvoiceSchema
from .payment import Payment, PaymentSchema
from .payment_account import PaymentAccount, PaymentAccountSchema
from .refund import Refund, RefundSchema


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
        PaymentAccount,
        primaryjoin="and_(RoutingSlip.payment_account_id == PaymentAccount.id)",
        foreign_keys=[payment_account_id],
        lazy="select",
        innerjoin=True,
    )
    payments = relationship(
        Payment,
        primaryjoin="and_(RoutingSlip.payment_account_id == foreign(Payment.payment_account_id))",
        viewonly=True,
        lazy="joined",
    )

    invoices = relationship(
        Invoice,
        primaryjoin="and_(RoutingSlip.number == foreign(Invoice.routing_slip), "
        f"Invoice.payment_method_code.in_("
        f"['{PaymentMethod.INTERNAL.value}']))",
        viewonly=True,
        lazy="joined",
    )

    refunds = relationship(
        Refund,
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
    def find_children(cls, number: str) -> List[RoutingSlip]:
        """Return children for the routing slip."""
        return cls.query.filter_by(parent_number=number).all()

    @classmethod
    def find_by_payment_account_id(cls, payment_account_id: str) -> RoutingSlip:
        """Return a routing slip by payment account number."""
        return cls.query.filter_by(payment_account_id=payment_account_id).one_or_none()

    @classmethod
    def find_all_by_payment_account_id(cls, payment_account_id: str) -> List[RoutingSlip]:
        """Return a routing slip by payment account number."""
        return cls.query.filter_by(payment_account_id=payment_account_id).all()

    @classmethod
    def search(  # pylint: disable=too-many-arguments, too-many-locals
        cls,
        search_filter: Dict,
        page: int,
        limit: int,
        return_all: bool,
    ) -> (List[RoutingSlip], int):
        """Search for routing slips by the criteria provided."""
        query = (
            db.session.query(RoutingSlip)
            .outerjoin(RoutingSlip.payments)
            .outerjoin(RoutingSlip.payment_account)
            .outerjoin(RoutingSlip.invoices)
            .options(
                # This lazy loads all the invoice relationships.
                lazyload("*"),
                # load_only only loads the desired columns.
                load_only(
                    RoutingSlip.created_name,
                    RoutingSlip.status,
                    RoutingSlip.number,
                    RoutingSlip.routing_slip_date,
                    RoutingSlip.remaining_amount,
                    RoutingSlip.total,
                ),
                contains_eager(RoutingSlip.payments).load_only(
                    Payment.cheque_receipt_number,
                    Payment.receipt_number,
                    Payment.payment_method_code,
                    Payment.payment_status_code,
                ),
                contains_eager(RoutingSlip.payment_account).load_only(
                    PaymentAccount.name, PaymentAccount.payment_method
                ),
                contains_eager(RoutingSlip.invoices).load_only(
                    Invoice.routing_slip,
                    Invoice.folio_number,
                    Invoice.business_identifier,
                    Invoice.corp_type_code,
                ),
            )
        )

        if rs_number := search_filter.get("routingSlipNumber", None):
            query = query.filter(RoutingSlip.number.ilike("%" + rs_number + "%"))

        if status := search_filter.get("status", None):
            query = query.filter(RoutingSlip.status == status)

        if refund_status := search_filter.get("refundStatus", None):
            query = query.filter(RoutingSlip.refund_status == refund_status)

        if exclude_statuses := search_filter.get("excludeStatuses", None):
            query = query.filter(~RoutingSlip.status.in_(exclude_statuses))

        if total_amount := search_filter.get("totalAmount", None):
            query = query.filter(RoutingSlip.total == total_amount)

        if remaining_amount := search_filter.get("remainingAmount", None):
            query = query.filter(RoutingSlip.remaining_amount == cast(remaining_amount.replace("$", ""), Numeric))

        query = cls._add_date_filter(query, search_filter)

        if initiator := search_filter.get("initiator", None):
            query = query.filter(RoutingSlip.created_name.ilike("%" + initiator + "%"))  # pylint: disable=no-member

        if business_identifier := search_filter.get("businessIdentifier", None):
            query = query.filter(Invoice.business_identifier == business_identifier)

        query = cls._add_receipt_number(query, search_filter)

        query = cls._add_folio_filter(query, search_filter)

        query = cls._add_entity_filter(query, search_filter)

        # Add ordering
        query = query.order_by(RoutingSlip.created_on.desc())

        if not return_all:
            sub_query = (
                query.with_entities(RoutingSlip.id)
                .group_by(RoutingSlip.id)
                .limit(limit)
                .offset((page - 1) * limit)
                .subquery()
            )
            query = query.filter(RoutingSlip.id.in_(sub_query.select()))

        result = query.all()
        count = len(result)

        return result, count

    @classmethod
    def _add_date_filter(cls, query, search_filter):
        # Find start and end dates for folio search
        created_from: datetime = None
        created_to: datetime = None

        if end_date := get_str_by_path(search_filter, "dateFilter/endDate"):
            created_to = datetime.strptime(end_date, DT_SHORT_FORMAT)
        if start_date := get_str_by_path(search_filter, "dateFilter/startDate"):
            created_from = datetime.strptime(start_date, DT_SHORT_FORMAT)
        # if passed in details
        if created_to and created_from:
            # Truncate time for from date and add max time for to date
            tz_name = current_app.config["LEGISLATIVE_TIMEZONE"]
            tz_local = pytz.timezone(tz_name)

            created_from = created_from.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(tz_local)
            created_to = created_to.replace(hour=23, minute=59, second=59, microsecond=999999).astimezone(tz_local)

            # If the dateFilter/target is provided then filter on that column, else filter on routing_slip_date
            target_date = getattr(
                RoutingSlip,
                get_str_by_path(search_filter, "dateFilter/target") or "routing_slip_date",
            )

            query = query.filter(
                func.timezone(tz_name, func.timezone("UTC", target_date)).between(created_from, created_to)
            )
        return query

    @classmethod
    def _add_receipt_number(cls, query, search_filter):
        conditions = []
        if receipt_number := search_filter.get("receiptNumber", None):
            conditions.append(
                and_(
                    Payment.payment_account_id == PaymentAccount.id,
                    and_(
                        Payment.cheque_receipt_number == receipt_number,
                        Payment.payment_method_code == PaymentMethod.CASH.value,
                    ),
                )
            )
        if cheque_receipt_number := search_filter.get("chequeReceiptNumber", None):
            conditions.append(
                and_(
                    Payment.payment_account_id == PaymentAccount.id,
                    and_(
                        Payment.cheque_receipt_number == cheque_receipt_number,
                        Payment.payment_method_code == PaymentMethod.CHEQUE.value,
                    ),
                )
            )
        if conditions:
            query = query.filter(*conditions)
        return query

    @classmethod
    def _add_folio_filter(cls, query, search_filter):
        if folio_number := search_filter.get("folioNumber", None):
            query = query.filter(Invoice.routing_slip == RoutingSlip.number).filter(
                Invoice.folio_number == folio_number
            )
        return query

    @classmethod
    def _add_entity_filter(cls, query, search_filter):
        if account_name := search_filter.get("accountName", None):
            query = query.filter(
                and_(
                    PaymentAccount.id == RoutingSlip.payment_account_id,
                    PaymentAccount.name.ilike("%" + account_name + "%"),
                )
            )
        return query


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
