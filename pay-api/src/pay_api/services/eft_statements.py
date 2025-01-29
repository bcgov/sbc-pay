# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Service to support EFT statements."""
from __future__ import annotations

from sqlalchemy import and_, func, select

from pay_api.models import EFTCreditInvoiceLink as EFTCreditInvoiceLinkModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Statement as StatementModel
from pay_api.models import StatementInvoices as StatementInvoicesModel
from pay_api.models import db
from pay_api.utils.enums import EFTCreditInvoiceStatus, InvoiceStatus, PaymentMethod


class EFTStatements:
    """Service to support EFT statements."""

    @staticmethod
    def get_statement_summary_query():
        """Query for latest statement id and total amount owing of invoices in statements."""
        return (
            db.session.query(
                StatementModel.payment_account_id,
                func.max(StatementModel.id).label("latest_statement_id"),
                func.coalesce(func.sum(InvoiceModel.total - InvoiceModel.paid), 0).label("total_owing"),
            )
            .join(
                StatementInvoicesModel,
                StatementInvoicesModel.statement_id == StatementModel.id,
            )
            .join(
                InvoiceModel,
                and_(
                    InvoiceModel.id == StatementInvoicesModel.invoice_id,
                    InvoiceModel.payment_method_code == PaymentMethod.EFT.value,
                ),
            )
            .filter(
                InvoiceModel.invoice_status_code.notin_(
                    [
                        InvoiceStatus.CANCELLED.value,
                        InvoiceStatus.REFUND_REQUESTED.value,
                        InvoiceStatus.REFUNDED.value,
                    ]
                )
            )
            .group_by(StatementModel.payment_account_id)
        )

    @staticmethod
    def get_statements_owing_as_array():
        """Query EFT Statements with outstanding balances and pending payments."""
        pending_payments_subquery = (
            select(
                func.count().label("cnt"),
                StatementInvoicesModel.statement_id,
                func.sum(EFTCreditInvoiceLinkModel.amount).label("pending_payment_amount"),
            )
            .select_from(EFTCreditInvoiceLinkModel)
            .join(StatementInvoicesModel, StatementInvoicesModel.invoice_id == EFTCreditInvoiceLinkModel.invoice_id)
            .where(EFTCreditInvoiceLinkModel.status_code == EFTCreditInvoiceStatus.PENDING.value)
            .group_by(StatementInvoicesModel.statement_id)
            .alias("pending_payments")
        )

        statements_subquery = (
            select(
                StatementModel.id,
                StatementModel.payment_account_id,
                func.sum(InvoiceModel.total - InvoiceModel.paid).label("amount_owing"),
                func.coalesce(pending_payments_subquery.c.cnt, 0).label("pending_payments_count"),
                func.coalesce(pending_payments_subquery.c.pending_payment_amount, 0).label("pending_payments_amount"),
            )
            .select_from(StatementModel)
            .join(StatementInvoicesModel, StatementInvoicesModel.statement_id == StatementModel.id)
            .join(InvoiceModel, InvoiceModel.id == StatementInvoicesModel.invoice_id)
            .outerjoin(pending_payments_subquery, pending_payments_subquery.c.statement_id == StatementModel.id)
            .where(
                and_(
                    StatementModel.payment_account_id == PaymentAccountModel.id,
                    InvoiceModel.invoice_status_code.in_([InvoiceStatus.APPROVED.value, InvoiceStatus.OVERDUE.value]),
                    InvoiceModel.payment_method_code == PaymentMethod.EFT.value,
                )
            )
            .group_by(
                StatementModel.id,
                StatementModel.payment_account_id,
                pending_payments_subquery.c.cnt,
                pending_payments_subquery.c.pending_payment_amount,
            )
            .having(func.sum(InvoiceModel.total - InvoiceModel.paid) > 0)
            .order_by(StatementModel.id)
            .subquery()
        )

        json_array = func.json_agg(
            func.json_build_object(
                "statement_id",
                statements_subquery.c.id,
                "amount_owing",
                statements_subquery.c.amount_owing,
                "pending_payments_count",
                statements_subquery.c.pending_payments_count,
                "pending_payments_amount",
                statements_subquery.c.pending_payments_amount,
            )
        )
        return (
            db.session.query(PaymentAccountModel.id, json_array.label("statements"))
            .join(statements_subquery, PaymentAccountModel.id == statements_subquery.c.payment_account_id)
            .filter(PaymentAccountModel.payment_method == PaymentMethod.EFT.value)
            .group_by(PaymentAccountModel.id)
        )
