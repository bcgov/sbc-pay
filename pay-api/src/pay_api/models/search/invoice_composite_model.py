# Copyright © 2025 Province of British Columbia
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
"""Composite Model to handle invoice search queries."""

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import column_property
from sqlalchemy.orm.decl_api import declared_attr

from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentMethod
from pay_api.models import Refund as RefundModel
from pay_api.utils.enums import InvoiceStatus


def get_latest_refund_subq():
    """Get the latest refund subquery."""
    return (
        select(RefundModel.id.label("refund_id"), RefundModel.status.label("refund_status"))
        .where(RefundModel.invoice_id == InvoiceModel.id)
        .order_by(RefundModel.id.desc())
        .limit(1)
        .correlate(InvoiceModel)
        .subquery()
    )


def get_latest_refund_id_expr():
    """Get the latest refund ID expression."""
    latest_refund_subq = get_latest_refund_subq()
    return select(latest_refund_subq.c.refund_id).scalar_subquery()


def get_latest_refund_status_expr():
    """Get the latest refund status expression."""
    latest_refund_subq = get_latest_refund_subq()
    return select(latest_refund_subq.c.refund_status).scalar_subquery()


def get_full_refundable_expr():
    """Get the full refundable expression."""
    return (
        exists()
        .where(
            and_(
                PaymentMethod.code == InvoiceModel.payment_method_code,
                InvoiceModel.invoice_status_code == func.any(PaymentMethod.full_refund_statuses),
            )
        )
        .label("full_refundable")
    )


def get_partial_refundable_expr():
    """Get the partial refundable expression."""
    return (
        exists()
        .where(
            and_(
                PaymentMethod.code == InvoiceModel.payment_method_code,
                PaymentMethod.partial_refund.is_(True),
                InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value,
                InvoiceModel.refund_date.is_(None),
            )
        )
        .label("partial_refundable")
    )


class InvoiceCompositeModel(InvoiceModel):
    """This class is a composite of the Invoice and other additional information required for search results."""

    @declared_attr
    def latest_refund_id(self):
        """Latest refund ID as a column property."""
        return column_property(get_latest_refund_id_expr())

    @declared_attr
    def latest_refund_status(self):
        """Latest refund status as a column property."""
        return column_property(get_latest_refund_status_expr())

    @declared_attr
    def full_refundable(self):
        """Full refundable indicator as a column property."""
        return column_property(get_full_refundable_expr())

    @declared_attr
    def partial_refundable(self):
        """Partial refundable indicator as a column property."""
        return column_property(get_partial_refundable_expr())
