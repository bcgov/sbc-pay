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
"""Send a one-time payment reminder to payers with unclaimed express-checkout invoices.

Runs daily. For each invoice_payment_links row where:
  - the payer supplied an email at creation time
  - the link has not yet been redeemed (linked_at IS NULL)
  - the reminder has not already been sent (notified_at IS NULL)
  - the link is at least EXPRESS_CHECKOUT_REMINDER_AFTER_DAYS old

publish one reminder message to ACCOUNT_MAILER_TOPIC and stamp notified_at.
"""

from datetime import UTC, datetime, timedelta

from flask import current_app

from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import db
from utils.mailer import publish_express_checkout_reminder


class ExpressCheckoutReminderTask:  # pylint: disable=too-few-public-methods
    """Publish a single reminder per unclaimed express-checkout invoice to the account mailer queue."""

    @classmethod
    def notify_unpaid_invoices(cls) -> int:
        """Query and notify. Returns the number of reminders successfully published."""
        reminder_after_days = current_app.config["EXPRESS_CHECKOUT_REMINDER_AFTER_DAYS"]
        cutoff = datetime.now(tz=UTC) - timedelta(days=reminder_after_days)

        candidates = (
            db.session.query(InvoiceModel, InvoicePaymentLinkModel)
            .join(InvoicePaymentLinkModel, InvoicePaymentLinkModel.invoice_id == InvoiceModel.id)
            .filter(InvoicePaymentLinkModel.linked_at.is_(None))
            .filter(InvoicePaymentLinkModel.email.isnot(None))
            .filter(InvoicePaymentLinkModel.notified_at.is_(None))
            .filter(InvoicePaymentLinkModel.created_at <= cutoff)
            .all()
        )

        current_app.logger.info("ExpressCheckoutReminderTask: %s candidates found", len(candidates))

        base_url = current_app.config.get("EXPRESS_CHECKOUT_URL", "").rstrip("/")
        sent = 0
        for invoice, link in candidates:
            try:
                payment_url = f"{base_url}/pay/{link.token}"
                description = ", ".join(
                    li.description
                    for li in (invoice.payment_line_items or [])
                    if li.description
                )
                default_ttl = current_app.config.get("PAYMENT_LINK_TOKEN_TTL_DAYS", 30)
                ttl_days = (invoice.corp_type.payment_link_ttl_days or default_ttl)
                expiry_date = link.created_at + timedelta(days=ttl_days)
                expiry_days = (expiry_date.date() - datetime.now(tz=UTC).date()).days
                expiry_date_str = f"{expiry_date.strftime('%B')} {expiry_date.day}, {expiry_date.year}"
                publish_express_checkout_reminder(
                    email=link.email,
                    payment_url=payment_url,
                    total=f"{invoice.total:,.2f}",
                    description=description,
                    expiry_days=expiry_days,
                    expiry_date=expiry_date_str,
                )
                link.notified_at = datetime.now(tz=UTC)
                db.session.commit()
                sent += 1
            except Exception:  # pylint: disable=broad-except
                db.session.rollback()
                current_app.logger.exception(
                    "ExpressCheckoutReminderTask failed for invoice_id=%s link_token=%s",
                    invoice.id,
                    link.token,
                )

        current_app.logger.info(
            "ExpressCheckoutReminderTask published %s/%s reminders (after_days=%s)",
            sent,
            len(candidates),
            reminder_after_days,
        )
        return sent
