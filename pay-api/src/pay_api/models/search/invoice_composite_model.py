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

from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentMethod
from pay_api.models import Refund as RefundModel
from pay_api.utils.enums import InvoiceStatus


class InvoiceCompositeModel(InvoiceModel):
    """This class is a composite of the Invoice and other additional information required for search results."""

    latest_refund_subq = (
        select(RefundModel.id.label("refund_id"), RefundModel.status.label("refund_status"))
        .where(RefundModel.invoice_id == InvoiceModel.id)
        .order_by(RefundModel.id.desc())
        .limit(1)
        .correlate(InvoiceModel)
        .subquery()
    )

    latest_refund_id_expr = select(latest_refund_subq.c.refund_id).scalar_subquery()

    latest_refund_status_expr = select(latest_refund_subq.c.refund_status).scalar_subquery()

    full_refundable_expr = (
        exists()
        .where(
            and_(
                PaymentMethod.code == InvoiceModel.payment_method_code,
                InvoiceModel.invoice_status_code == func.any(PaymentMethod.full_refund_statuses),
            )
        )
        .label("full_refundable")
    )

    partial_refundable_expr = (
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

    latest_refund_id = column_property(latest_refund_id_expr)
    latest_refund_status = column_property(latest_refund_status_expr)
    full_refundable = column_property(full_refundable_expr)
    partial_refundable = column_property(partial_refundable_expr)
