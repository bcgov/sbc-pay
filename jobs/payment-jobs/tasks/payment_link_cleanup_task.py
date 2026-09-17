# Copyright © 2026 Province of British Columbia
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
"""Mark expired, unclaimed payment link invoices as DELETED.

Retention per corp type: `corp_types.payment_link_ttl_days` when set, else the global
`PAYMENT_LINK_TOKEN_TTL_DAYS` config.

For each expired unclaimed link (`linked_at IS NULL` and past TTL) whose invoice is
still CREATED, run it through PaymentService.delete_invoice — that cancels the CFS
reference and marks the invoice / line items / payment records DELETED via the
existing flow. Link rows are NOT deleted; they're the audit trail of which token
pointed at which invoice.
"""

from datetime import UTC, datetime, timedelta

from flask import current_app

from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import db
from pay_api.services.payment_service import PaymentService
from pay_api.utils.enums import InvoiceStatus


class PaymentLinkCleanupTask:  # pylint: disable=too-few-public-methods
    """Mark expired unclaimed express-checkout invoices as DELETED."""

    @classmethod
    def cleanup_expired_links(cls) -> int:
        """Process expired unclaimed links. Returns the count of invoices marked DELETED."""
        default_ttl = current_app.config["PAYMENT_LINK_TOKEN_TTL_DAYS"]
        now = datetime.now(tz=UTC)

        candidates = (
            db.session.query(InvoicePaymentLinkModel, InvoiceModel, CorpTypeModel)
            .join(InvoiceModel, InvoiceModel.id == InvoicePaymentLinkModel.invoice_id)
            .join(CorpTypeModel, CorpTypeModel.code == InvoiceModel.corp_type_code)
            .filter(InvoicePaymentLinkModel.linked_at.is_(None))
            .all()
        )

        deleted = 0
        for link, invoice, corp_type in candidates:
            ttl_days = corp_type.payment_link_ttl_days or default_ttl
            if link.created_at >= now - timedelta(days=ttl_days):
                continue
            if invoice.invoice_status_code != InvoiceStatus.CREATED.value:
                continue
            try:
                PaymentService.delete_invoice(invoice.id)
                db.session.commit()
                deleted += 1
            except Exception as exc:  # pylint: disable=broad-except
                db.session.rollback()
                current_app.logger.exception(
                    "PaymentLinkCleanupTask failed for token=%s invoice_id=%s: %s",
                    link.token,
                    invoice.id,
                    exc,
                )

        current_app.logger.info(
            "PaymentLinkCleanupTask marked %s expired unclaimed invoices as DELETED (default_ttl=%s days)",
            deleted,
            default_ttl,
        )
        return deleted
