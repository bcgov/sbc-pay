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
"""Delete expired / consumed / invalidated invoice_payment_link rows.

Sized against the sparse partner-link table, not `invoices`; safe to run daily.
"""

from datetime import UTC, datetime, timedelta

from flask import current_app

from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import db


class PaymentLinkCleanupTask:  # pylint: disable=too-few-public-methods
    """Task to hard-delete stale payment link tokens."""

    @classmethod
    def cleanup_expired_links(cls) -> int:
        """Delete rows that are consumed, invalidated, or past TTL. Returns deleted count."""
        ttl_days = int(current_app.config.get("PAYMENT_LINK_TOKEN_TTL_DAYS", 30))
        cutoff = datetime.now(tz=UTC) - timedelta(days=ttl_days)

        deleted = (
            db.session.query(InvoicePaymentLinkModel)
            .filter(
                (InvoicePaymentLinkModel.linked_at.isnot(None))
                | (InvoicePaymentLinkModel.invalidated_at.isnot(None))
                | (InvoicePaymentLinkModel.created_at < cutoff)
            )
            .delete(synchronize_session=False)
        )
        db.session.commit()

        current_app.logger.info(
            "PaymentLinkCleanupTask deleted %s expired/consumed link rows (ttl=%s days)", deleted, ttl_days
        )
        return deleted
