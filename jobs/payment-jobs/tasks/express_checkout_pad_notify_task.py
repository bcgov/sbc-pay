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
"""Drain the held partner notifications for express-checkout PAD invoices.

For each express-checkout PAD invoice that reached PAID at least
`EXPRESS_CHECKOUT_PAD_HOLD_DAYS` business days ago and has not yet been
notified (invoice_payment_links.partner_notified_at IS NULL), publish the
payment event to the partner topic and stamp the timestamp.

If a reversal happened during the hold window, the invoice will no longer
be in PAID status and this job will naturally skip it — the NSF flow
publishes the reversal on its own.
"""

from datetime import UTC, datetime

from flask import current_app
from sbc_common_components.utils.enums import QueueMessageTypes

from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import db
from pay_api.services import gcp_queue_publisher
from pay_api.services.gcp_queue_publisher import QueueMessage
from pay_api.services.payment_transaction import PaymentTransaction as PaymentTransactionService
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, PaymentStatus, QueueSources
from pay_api.utils.util import get_topic_for_corp_type, subtract_business_days


class ExpressCheckoutPadNotifyTask:  # pylint: disable=too-few-public-methods
    """Publish held partner notifications for express-checkout PAD invoices past the hold window."""

    @classmethod
    def notify_due_invoices(cls) -> int:
        """Publish + stamp for every due invoice. Returns the count published."""
        hold_days = current_app.config["EXPRESS_CHECKOUT_PAD_HOLD_DAYS"]
        cutoff = subtract_business_days(datetime.now(tz=UTC), hold_days)

        candidates = (
            db.session.query(InvoiceModel)
            .join(CorpTypeModel, CorpTypeModel.code == InvoiceModel.corp_type_code)
            .filter(CorpTypeModel.is_express_checkout_enabled.is_(True))
            .filter(InvoiceModel.payment_method_code == PaymentMethod.PAD.value)
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value)
            .filter(InvoiceModel.payment_date.isnot(None))
            .filter(InvoiceModel.payment_date <= cutoff)
            .all()
        )

        published = 0
        for invoice in candidates:
            link = (
                db.session.query(InvoicePaymentLinkModel)
                .filter(InvoicePaymentLinkModel.invoice_id == invoice.id)
                .filter(InvoicePaymentLinkModel.partner_notified_at.is_(None))
                .first()
            )
            if not link:
                current_app.logger.warning(
                    "ExpressCheckoutPadNotifyTask: no unnotified link row for invoice_id=%s; skipping.",
                    invoice.id,
                )
                continue

            try:
                cls._publish(invoice)
                link.partner_notified_at = datetime.now(tz=UTC)
                db.session.commit()
                published += 1
            except Exception as exc:  # pylint: disable=broad-except
                db.session.rollback()
                current_app.logger.exception(
                    "ExpressCheckoutPadNotifyTask failed for invoice_id=%s: %s", invoice.id, exc
                )

        current_app.logger.info(
            "ExpressCheckoutPadNotifyTask published %s express-checkout PAD notifications (hold_days=%s)",
            published,
            hold_days,
        )
        return published

    @staticmethod
    def _publish(invoice: InvoiceModel) -> None:
        """Publish the PAID event with a paidAt attribute the partner can key on."""
        status_code = PaymentStatus.COMPLETED.value
        payload = PaymentTransactionService.create_event_payload(invoice=invoice, status_code=status_code)
        attributes = {
            "statusCode": status_code,
            "corpTypeCode": invoice.corp_type_code,
            "paymentMethod": invoice.payment_method_code,
        }
        if invoice.payment_date:
            attributes["paidAt"] = invoice.payment_date.isoformat()

        gcp_queue_publisher.publish_to_queue(
            QueueMessage(
                source=QueueSources.PAY_JOBS.value,
                message_type=QueueMessageTypes.PAYMENT.value,
                payload=payload,
                topic=get_topic_for_corp_type(invoice.corp_type_code),
                corp_type=invoice.corp_type_code,
                attributes=attributes,
            )
        )
