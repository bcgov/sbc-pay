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
"""Model for the invoice_payment_link table (nanoid → invoice binding for external invoices)."""

from datetime import UTC, datetime

from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db


class InvoicePaymentLink(BaseModel):
    """Opaque payment-link token bound to a single invoice.

    Only invoices created via the external / service-account flow get a row.
    """

    __tablename__ = "invoice_payment_links"
    __mapper_args__ = {
        "include_properties": [
            "token",
            "invoice_id",
            "created_at",
            "linked_at",
            "partner_notified_at",
            "email",
            "return_url",
        ]
    }

    token = db.Column(db.String(32), primary_key=True)
    invoice_id = db.Column(db.Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=UTC))
    linked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Stamped by the express-checkout PAD notify job after the CAS reversal window elapses.
    partner_notified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Captured at invoice creation time for unlinked-invoice notification delivery.
    email = db.Column(db.String(254), nullable=True)
    return_url = db.Column(db.String(2048), nullable=True)

    @classmethod
    def find_by_token(cls, token: str) -> "InvoicePaymentLink | None":
        """Return the link row for a token, regardless of state."""
        return cls.query.filter_by(token=token).one_or_none()

    @classmethod
    def find_unredeemed_for_invoice(cls, invoice_id: int) -> "InvoicePaymentLink | None":
        """Return the invoice's link row if nobody has claimed it yet, else None."""
        link = cls.query.filter_by(invoice_id=invoice_id).one_or_none()
        return link if link is not None and link.linked_at is None else None

    @classmethod
    def is_unredeemed_for_invoice(cls, invoice_id: int) -> bool:
        """Return True if the invoice has a link row nobody has claimed yet."""
        return cls.find_unredeemed_for_invoice(invoice_id) is not None
