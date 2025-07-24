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

from datetime import datetime
from typing import Dict

import pytz
from attrs import define
from flask import current_app
from marshmallow import fields
from sqlalchemy import Boolean, ForeignKey, String, and_, cast, exists, func, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.orm import contains_eager, joinedload, lazyload, load_only, relationship

from pay_api.exceptions import BusinessException
from pay_api.utils.constants import DT_SHORT_FORMAT
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus
from pay_api.utils.enums import PaymentMethod as PaymentMethodEnum
from pay_api.utils.enums import PaymentStatus
from pay_api.utils.errors import Error
from pay_api.utils.sqlalchemy import JSONPath
from pay_api.utils.util import get_first_and_last_dates_of_month, get_str_by_path, get_week_start_and_end_date

from .applied_credits import AppliedCredits
from .base_model import BaseModel
from .base_schema import BaseSchema
from .corp_type import CorpType
from .db import db
from .fee_schedule import FeeSchedule
from .invoice import Invoice
from .invoice_reference import InvoiceReference
from .payment_account import PaymentAccount
from .payment_line_item import PaymentLineItem
from .payment_method import PaymentMethod
from .payment_status_code import PaymentStatusCode
from .payment_system import PaymentSystem
from .refunds_partial import RefundsPartial


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

    @classmethod
    def generate_base_transaction_query(cls, include_credits_and_partial_refunds: bool):
        """Generate a base query."""
        options = [
            lazyload("*"),
            load_only(
                Invoice.id,
                Invoice.corp_type_code,
                Invoice.created_on,
                Invoice.payment_date,
                Invoice.refund_date,
                Invoice.invoice_status_code,
                Invoice.total,
                Invoice.service_fees,
                Invoice.paid,
                Invoice.refund,
                Invoice.folio_number,
                Invoice.created_name,
                Invoice.invoice_status_code,
                Invoice.payment_method_code,
                Invoice.details,
                Invoice.business_identifier,
                Invoice.created_by,
                Invoice.filing_id,
                Invoice.bcol_account,
                Invoice.disbursement_date,
                Invoice.disbursement_reversal_date,
                Invoice.overdue_date,
            ),
            contains_eager(Invoice.payment_line_items)
            .load_only(
                PaymentLineItem.description,
                PaymentLineItem.gst,
                PaymentLineItem.pst,
                PaymentLineItem.service_fees,
                PaymentLineItem.total,
            )
            .contains_eager(PaymentLineItem.fee_schedule)
            .load_only(FeeSchedule.filing_type_code),
            contains_eager(Invoice.payment_account).load_only(
                PaymentAccount.auth_account_id,
                PaymentAccount.name,
                PaymentAccount.billable,
                PaymentAccount.branch_name,
            ),
            contains_eager(Invoice.references).load_only(
                InvoiceReference.invoice_number,
                InvoiceReference.reference_number,
                InvoiceReference.status_code,
            ),
        ]

        if include_credits_and_partial_refunds:
            options.extend([joinedload(Invoice.applied_credits), joinedload(Invoice.partial_refunds)])

        return (
            db.session.query(Invoice)
            .join(PaymentAccount, Invoice.payment_account_id == PaymentAccount.id)
            .join(PaymentLineItem, PaymentLineItem.invoice_id == Invoice.id)
            .join(
                FeeSchedule,
                FeeSchedule.fee_schedule_id == PaymentLineItem.fee_schedule_id,
            )
            .outerjoin(InvoiceReference, InvoiceReference.invoice_id == Invoice.id)
            .options(*options)
        )

    @classmethod
    def search_without_counts(cls, params: TransactionSearchParams):
        """Search without using counts, ideally this will become our baseline."""
        query = cls.generate_base_transaction_query(include_credits_and_partial_refunds=True)
        query = cls.filter(query, params.auth_account_id, params.search_filter)
        # Grab +1, so we can check if there are more records.
        params.limit += 1
        sub_query = cls.generate_subquery(params).subquery()
        results = query.filter(Invoice.id.in_(sub_query.select())).order_by(Invoice.id.desc()).all()
        has_more = len(results) > params.limit
        return results[: params.limit], has_more

    @classmethod
    def search_purchase_history(  # noqa:E501; pylint:disable=too-many-arguments, too-many-locals, too-many-branches, too-many-statements;
        cls, auth_account_id: str, search_filter: Dict, page: int, limit: int, return_all: bool, max_no_records: int = 0
    ):
        """Search for purchase history."""
        executor = current_app.extensions["flask_executor"]
        query = cls.generate_base_transaction_query(include_credits_and_partial_refunds=False)
        query = cls.filter(query, auth_account_id, search_filter)
        if not return_all:
            count_future = executor.submit(cls.get_count, auth_account_id, search_filter)
            sub_query = cls.generate_subquery(
                TransactionSearchParams(
                    auth_account_id=auth_account_id, search_filter=search_filter, page=page, limit=limit
                )
            )
            query = query.filter(Invoice.id.in_(sub_query.subquery().select())).order_by(Invoice.id.desc())
            result_future = executor.submit(query.all)
            count = count_future.result()
            result = result_future.result()
            # If maximum number of records is provided, return it as total
            if max_no_records > 0:
                count = max_no_records if max_no_records < count else count
        elif max_no_records > 0:
            # If maximum number of records is provided, set the page with that number
            sub_query = cls.generate_subquery(
                TransactionSearchParams(auth_account_id, search_filter, limit=max_no_records, page=None)
            )
            result, count = (
                query.filter(Invoice.id.in_(sub_query.subquery().select())).all(),
                sub_query.count(),
            )
        else:
            count = cls.get_count(auth_account_id, search_filter)
            if count > 100000:
                raise BusinessException(Error.PAYMENT_SEARCH_TOO_MANY_RECORDS)
            result = query.all()
        return result, count

    @classmethod
    def get_invoices_and_payment_accounts_for_statements(cls, search_filter: Dict):
        """Slimmed down version for statements."""
        auth_account_ids = select(func.unnest(cast(search_filter.get("authAccountIds", []), ARRAY(TEXT))))
        query = (
            db.session.query(Invoice)
            .join(PaymentAccount, Invoice.payment_account_id == PaymentAccount.id)
            .filter(PaymentAccount.auth_account_id.in_(auth_account_ids))
        )
        # If an account is within these payment methods - limit invoices to these payment methods.
        # Used for transitioning payment method and an interim statement is created (There could be different payment
        # methods for the transition day and we don't want it on both statements)
        if search_filter.get("matchPaymentMethods", None):
            query = query.filter(
                or_(
                    and_(
                        PaymentAccount.payment_method == PaymentMethodEnum.EFT.value,
                        Invoice.payment_method_code == PaymentAccount.payment_method,
                    ),
                    and_(
                        PaymentAccount.payment_method != PaymentMethodEnum.EFT.value,
                        Invoice.payment_method_code != PaymentMethodEnum.EFT.value,
                    ),
                )
            )

        query = cls.filter_date(query, search_filter).with_entities(
            Invoice.id,
            Invoice.payment_method_code,
            PaymentAccount.auth_account_id,
            PaymentAccount.id.label("payment_account_id"),
        )
        return query.all()

    @classmethod
    def get_count(cls, auth_account_id: str, search_filter: Dict):
        """Slimmed downed version for count (less joins)."""
        query = db.session.query(func.distinct(Invoice.id))
        query = cls.filter(query, auth_account_id, search_filter, include_joins=True)
        count = query.count()
        return count

    @classmethod
    def filter(cls, query, auth_account_id: str, search_filter: Dict, include_joins=False):
        """For filtering queries."""
        query = cls.filter_payment_account(query, auth_account_id, search_filter, include_joins)
        if status_code := search_filter.get("statusCode", None):
            query = cls._apply_status_filter(query, status_code)

        # Handle deprecated status filtering
        if status := search_filter.get("status", None):
            query = cls._apply_status_filter(query, status)
        if search_filter.get("folioNumber", None):
            query = query.filter(Invoice.folio_number == search_filter.get("folioNumber"))
        if business_identifier := search_filter.get("businessIdentifier", None):
            query = query.filter(Invoice.business_identifier.ilike(f"%{business_identifier}%"))
        if created_by := search_filter.get("createdBy", None):  # pylint: disable=no-member
            # depreciating (replacing with createdName)
            query = query.filter(Invoice.created_name.ilike(f"%{created_by}%"))  # pylint: disable=no-member
        if created_name := search_filter.get("createdName", None):
            query = query.filter(Invoice.created_name.ilike(f"%{created_name}%"))  # pylint: disable=no-member
        if invoice_id := search_filter.get("id", None):
            query = query.filter(cast(Invoice.id, String).like(f"%{invoice_id}%"))
        if invoice_number := search_filter.get("invoiceNumber", None):
            if include_joins:
                query = query.join(InvoiceReference, InvoiceReference.invoice_id == Invoice.id)
            query = query.filter(InvoiceReference.invoice_number.ilike(f"%{invoice_number}%"))

        query = cls.filter_corp_type(query, search_filter)
        query = cls.filter_payment(query, search_filter)
        query = cls.filter_details(query, search_filter, include_joins)
        query = cls.filter_date(query, search_filter)
        return query

    @classmethod
    def _apply_status_filter(cls, query, status_code: str):
        """Apply status filter to query."""
        if status_code == InvoiceStatus.PARTIALLY_CREDITED.value:
            return query.filter(
                exists().where(and_(RefundsPartial.invoice_id == Invoice.id, RefundsPartial.is_credit.is_(True)))
            )
        elif status_code == InvoiceStatus.PARTIALLY_REFUNDED.value:
            return query.filter(
                exists().where(and_(RefundsPartial.invoice_id == Invoice.id, RefundsPartial.is_credit.is_(False)))
            )
        else:
            return query.filter(Invoice.invoice_status_code == status_code)

    @classmethod
    def _apply_payment_method_filter(cls, query, payment_type: str):
        """Apply payment method filter to query."""
        if payment_type == "NO_FEE":
            return query.filter(Invoice.total == 0)
        elif payment_type == PaymentMethodEnum.CREDIT.value:
            # For CREDIT, include invoices where sum of AppliedCredits equals invoice total
            credit_total_subquery = (
                select(AppliedCredits.invoice_id, func.sum(AppliedCredits.amount_applied).label("total_applied"))
                .group_by(AppliedCredits.invoice_id)
                .subquery()
            )

            return query.join(credit_total_subquery, credit_total_subquery.c.invoice_id == Invoice.id).filter(
                and_(Invoice.total != 0, credit_total_subquery.c.total_applied == Invoice.total)
            )
        elif payment_type in [PaymentMethodEnum.PAD.value, PaymentMethodEnum.ONLINE_BANKING.value]:
            # For PAD and ONLINE_BANKING, exclude invoices where sum of AppliedCredits equals invoice total
            credit_total_subquery = (
                select(AppliedCredits.invoice_id, func.sum(AppliedCredits.amount_applied).label("total_applied"))
                .group_by(AppliedCredits.invoice_id)
                .subquery()
            )

            return query.outerjoin(credit_total_subquery, credit_total_subquery.c.invoice_id == Invoice.id).filter(
                and_(
                    Invoice.total != 0,
                    Invoice.payment_method_code == payment_type,
                    or_(
                        credit_total_subquery.c.total_applied.is_(None),
                        credit_total_subquery.c.total_applied != Invoice.total,
                    ),
                )
            )
        else:
            return query.filter(Invoice.total != 0).filter(Invoice.payment_method_code == payment_type)

    @classmethod
    def filter_payment_account(cls, query, auth_account_id, search_filter: dict, include_joins=False):
        """Use subquery to look for payment accounts ahead of time, much faster and easier."""
        account_name = search_filter.get("accountName", None)
        if auth_account_id:
            payment_account_id = (
                db.session.query(PaymentAccount.id).filter(PaymentAccount.auth_account_id == auth_account_id).scalar()
            )
            query = query.filter(Invoice.payment_account_id == (payment_account_id or -1))
        if account_name:
            if include_joins:
                query = query.join(PaymentAccount, PaymentAccount.id == Invoice.payment_account_id)
            query = query.filter(PaymentAccount.name.ilike(f"%{account_name}%"))
        return query

    @classmethod
    def filter_corp_type(cls, query, search_filter: dict):
        """Filter for corp type."""
        if product := search_filter.get("userProductCode", None):
            query = query.join(CorpType, CorpType.code == Invoice.corp_type_code).filter(CorpType.product == product)
        if product := search_filter.get("product", None):
            query = query.join(CorpType, CorpType.code == Invoice.corp_type_code).filter(CorpType.product == product)
        return query

    @classmethod
    def filter_payment(cls, query, search_filter: dict):
        """Filter for payment."""
        if payment_type := search_filter.get("paymentMethod", None):
            query = cls._apply_payment_method_filter(query, payment_type)
        return query

    @classmethod
    def filter_date(cls, query, search_filter: dict):
        """Filter by date."""
        # Find start and end dates
        created_from: datetime = None
        created_to: datetime = None
        if get_str_by_path(search_filter, "dateFilter/startDate"):
            created_from = datetime.strptime(get_str_by_path(search_filter, "dateFilter/startDate"), DT_SHORT_FORMAT)
        if get_str_by_path(search_filter, "dateFilter/endDate"):
            created_to = datetime.strptime(get_str_by_path(search_filter, "dateFilter/endDate"), DT_SHORT_FORMAT)
        if get_str_by_path(search_filter, "weekFilter/index"):
            created_from, created_to = get_week_start_and_end_date(
                index=int(get_str_by_path(search_filter, "weekFilter/index"))
            )
        if get_str_by_path(search_filter, "monthFilter/month") and get_str_by_path(search_filter, "monthFilter/year"):
            month = int(get_str_by_path(search_filter, "monthFilter/month"))
            year = int(get_str_by_path(search_filter, "monthFilter/year"))
            created_from, created_to = get_first_and_last_dates_of_month(month=month, year=year)

        if created_from and created_to:
            # Truncate time for from date and add max time for to date
            tz_name = current_app.config["LEGISLATIVE_TIMEZONE"]
            tz_local = pytz.timezone(tz_name)

            created_from = created_from.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(tz_local)
            created_to = created_to.replace(hour=23, minute=59, second=59, microsecond=999999).astimezone(tz_local)
            query = query.filter(
                func.timezone(tz_name, func.timezone("UTC", Invoice.created_on)).between(created_from, created_to)
            )
        return query

    @classmethod
    def filter_details(cls, query, search_filter: dict, include_joins=False):
        """Filter by details."""
        line_item = search_filter.get("lineItems", None)
        line_item_or_details = search_filter.get("lineItemsAndDetails", None)
        if (line_item or line_item_or_details) and include_joins:
            query = query.join(PaymentLineItem, PaymentLineItem.invoice_id == Invoice.id)
        if line_item:
            query = query.filter(PaymentLineItem.description.ilike(f"%{line_item}%"))
        if details := search_filter.get("details", None):
            query = query.filter(
                or_(
                    func.jsonb_path_exists(
                        Invoice.details, cast(f'$[*] ? (@.value like_regex "(?i).*{details}.*")', JSONPath())
                    ),
                    func.jsonb_path_exists(
                        Invoice.details, cast(f'$[*] ? (@.label like_regex "(?i).*{details}.*")', JSONPath())
                    ),
                )
            )
        if line_item_or_details:
            query = query.filter(
                or_(
                    PaymentLineItem.description.ilike(f"%{line_item_or_details}%"),
                    func.jsonb_path_exists(
                        Invoice.details,
                        cast(f'$[*] ? (@.value like_regex "(?i).*{line_item_or_details}.*")', JSONPath()),
                    ),
                    func.jsonb_path_exists(
                        Invoice.details,
                        cast(f'$[*] ? (@.label like_regex "(?i).*{line_item_or_details}.*")', JSONPath()),
                    ),
                )
            )

        return query

    @classmethod
    def generate_subquery(cls, params: TransactionSearchParams):
        """Generate subquery for invoices, used for pagination."""
        subquery = db.session.query(Invoice.id)
        subquery = (
            cls.filter(subquery, params.auth_account_id, params.search_filter, include_joins=True)
            .distinct()
            .order_by(Invoice.id.desc())
        )
        if params.limit:
            subquery = subquery.limit(params.limit)
        if params.limit and params.page:
            if params.no_counts:
                params.limit -= 1
            subquery = subquery.offset((params.page - 1) * params.limit)
        return subquery


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
    search_filter: Dict
    page: int
    limit: int
    no_counts: bool = False
