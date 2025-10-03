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
"""Model to handle all operations related to Payment data."""

from __future__ import annotations

from typing import Dict

from attrs import define
from marshmallow import fields
from sqlalchemy import Boolean, ForeignKey, or_
from sqlalchemy.orm import relationship

from pay_api.exceptions import BusinessException
from pay_api.utils.constants import DT_SHORT_FORMAT
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, PaymentStatus
from pay_api.utils.enums import PaymentMethod as PaymentMethodEnum
from pay_api.utils.errors import Error
from pay_api.utils.sqlalchemy import JSONPath
from pay_api.utils.util import get_first_and_last_dates_of_month, get_str_by_path, get_week_start_and_end_date

from ..utils.dataclasses import PurchaseHistorySearch  # noqa: TC001, TID252
from .applied_credits import AppliedCredits

from pay_api.utils.enums import InvoiceReferenceStatus
from pay_api.utils.enums import PaymentMethod as PaymentMethodEnum
from pay_api.utils.enums import PaymentStatus

from .base_model import BaseModel
from .base_schema import BaseSchema
from .db import db
from .invoice import Invoice
from .invoice_reference import InvoiceReference
from .payment_account import PaymentAccount
from .payment_method import PaymentMethod
from .payment_status_code import PaymentStatusCode
from .payment_system import PaymentSystem


class Payment(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Payment ."""

    __tablename__ = "payments"
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
            "cheque_receipt_number",
            "cons_inv_number",
            "created_by",
            "invoice_amount",
            "invoice_number",
            "is_routing_slip",
            "paid_amount",
            "paid_usd_amount",
            "payment_account_id",
            "payment_date",
            "payment_system_code",
            "payment_method_code",
            "payment_status_code",
            "receipt_number",
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_system_code = db.Column(db.String(10), ForeignKey("payment_systems.code"), nullable=False)
    payment_account_id = db.Column(db.Integer, ForeignKey("payment_accounts.id"), nullable=True, index=True)
    payment_method_code = db.Column(db.String(15), ForeignKey("payment_methods.code"), nullable=False)
    payment_status_code = db.Column(db.String(20), ForeignKey("payment_status_codes.code"), nullable=True)
    invoice_number = db.Column(db.String(50), nullable=True, index=True, comment="CFS Invoice number")
    receipt_number = db.Column(db.String(50), nullable=True, index=True, comment="CFS Receipt number")
    cheque_receipt_number = db.Column(
        db.String(50),
        nullable=True,
        index=True,
        comment="Cheque or cash receipt number",
    )
    is_routing_slip = db.Column(
        Boolean(),
        default=False,
        comment="Is the payment created as part of FAS by FAS User",
    )
    paid_amount = db.Column(db.Numeric(), nullable=True, comment="Amount PAID as part of payment")
    payment_date = db.Column(db.DateTime, nullable=True, comment="Date of payment")
    created_by = db.Column(
        db.String(50),
        default="SYSTEM",
        comment="Created user name, SYSTEM if job creates the record",
    )

    cons_inv_number = db.Column(db.String(50), nullable=True, index=True)
    invoice_amount = db.Column(db.Numeric(), nullable=True)
    paid_usd_amount = db.Column(db.Numeric(), nullable=True, comment="Amount PAID as part of payment in USD")
    # Capture payment made in USD

    payment_system = relationship(PaymentSystem, foreign_keys=[payment_system_code], lazy="select", innerjoin=True)
    payment_status = relationship(
        PaymentStatusCode,
        foreign_keys=[payment_status_code],
        lazy="select",
        innerjoin=True,
    )

    @classmethod
    def find_payment_method_by_payment_id(cls, identifier: int):
        """Return a Payment by id."""
        query = (
            db.session.query(PaymentMethod)
            .join(Payment)
            .filter(PaymentMethod.code == Payment.payment_method_code)
            .filter(Payment.id == identifier)
        )
        return query.one_or_none()

    @classmethod
    def find_payment_by_invoice_number_and_status(cls, inv_number: str, payment_status: str):
        """Return a Payment by invoice_number and status."""
        query = (
            db.session.query(Payment)
            .filter(Payment.invoice_number == inv_number)
            .filter(Payment.payment_status_code == payment_status)
        )
        return query.all()

    @classmethod
    def find_payment_by_receipt_number(cls, receipt_number: str):
        """Return a Payment by receipt_number."""
        return db.session.query(Payment).filter(Payment.receipt_number == receipt_number).one_or_none()

    @classmethod
    def find_payment_for_invoice(cls, invoice_id: int):
        """Find payment records created for the invoice."""
        query = (
            db.session.query(Payment)
            .join(
                InvoiceReference,
                InvoiceReference.invoice_number == Payment.invoice_number,
            )
            .join(Invoice, InvoiceReference.invoice_id == Invoice.id)
            .filter(Invoice.id == invoice_id)
            .filter(
                InvoiceReference.status_code.in_(
                    [
                        InvoiceReferenceStatus.ACTIVE.value,
                        InvoiceReferenceStatus.COMPLETED.value,
                    ]
                )
            )
        )

        return query.one_or_none()

    @classmethod
    def find_payments_for_routing_slip(cls, routing_slip: str):
        """Find payment records created for a routing slip."""
        return (
            db.session.query(Payment)
            .filter(Payment.receipt_number == routing_slip)
            .filter(Payment.is_routing_slip.is_(True))
            .all()
        )

    @classmethod
    def search_account_payments(cls, auth_account_id: str, payment_status: str, page: int, limit: int):
        """Search payment records created for the account."""
        query = (
            db.session.query(Payment, Invoice)
            .join(PaymentAccount, PaymentAccount.id == Payment.payment_account_id)
            .outerjoin(
                InvoiceReference,
                InvoiceReference.invoice_number == Payment.invoice_number,
            )
            .outerjoin(Invoice, InvoiceReference.invoice_id == Invoice.id)
            .filter(PaymentAccount.auth_account_id == auth_account_id)
        )

        if payment_status:
            query = query.filter(Payment.payment_status_code == payment_status)
            if payment_status == PaymentStatus.FAILED.value:
                consolidated_inv_subquery = (
                    db.session.query(Payment.invoice_number)
                    .filter(Payment.payment_status_code == PaymentStatus.CREATED.value)
                    .filter(Payment.payment_method_code == PaymentMethodEnum.CC.value)
                    .subquery()
                )

                # If call is to get NSF payments, get only active failed payments.
                # Exclude any payments which failed first and paid later.
                query = query.filter(
                    or_(
                        InvoiceReference.status_code == InvoiceReferenceStatus.ACTIVE.value,
                        Payment.cons_inv_number.in_(consolidated_inv_subquery.select()),
                    )
                )

        query = query.order_by(Payment.id.asc())
        pagination = query.paginate(per_page=limit, page=page)
        result, count = pagination.items, pagination.total

        return result, count

    @classmethod
    def find_payments_to_consolidate(cls, auth_account_id: str):
        """Find payments to be consolidated."""
        consolidated_inv_subquery = (
            db.session.query(Payment.cons_inv_number)
            .filter(Payment.payment_status_code == PaymentStatus.FAILED.value)
            .filter(Payment.payment_method_code == PaymentMethodEnum.PAD.value)
            .subquery()
        )

        query = (
            db.session.query(Payment)
            .join(PaymentAccount, PaymentAccount.id == Payment.payment_account_id)
            .outerjoin(
                InvoiceReference,
                InvoiceReference.invoice_number == Payment.invoice_number,
            )
            .filter(InvoiceReference.status_code == InvoiceReferenceStatus.ACTIVE.value)
            .filter(PaymentAccount.auth_account_id == auth_account_id)
            .filter(
                or_(
                    Payment.payment_status_code == PaymentStatus.FAILED.value,
                    Payment.invoice_number.in_(consolidated_inv_subquery.select()),
                )
            )
        )

        return query.all()

class PaymentSchema(BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Payment."""

    class Meta(BaseSchema.Meta):  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Payment
        exclude = [
            "payment_system",
            "payment_status",
            "payment_account_id",
            "cons_inv_number",
        ]

    payment_system_code = fields.String(data_key="payment_system")
    payment_method_code = fields.String(data_key="payment_method")
    payment_status_code = fields.String(data_key="status_code")
    invoice_amount = fields.Float(data_key="invoice_amount")
    paid_amount = fields.Float(data_key="paid_amount")
    cheque_receipt_number = fields.String(data_key="cheque_receipt_number")
    paid_usd_amount = fields.Float(data_key="paid_usd_amount")


@define
class TransactionSearchParams:
    """Parameters for search operations."""

    auth_account_id: str
    search_filter: dict
    page: int
    limit: int
    no_counts: bool = False
