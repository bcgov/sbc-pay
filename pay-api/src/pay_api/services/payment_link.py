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
"""Service for opaque payment link tokens used by the external-invoice flow.

Tokens are nanoids (21 chars, URL-safe alphabet, ~126 bits entropy) stored in
`invoice_payment_links`. Knowing a token allows a user to view an invoice
summary, link it to their auth account, and pay it — but not to enumerate
other invoices or view any invoice they weren't given the token for.
"""

from datetime import UTC, datetime, timedelta

from flask import current_app
from nanoid import generate as nanoid_generate

from pay_api.exceptions import BusinessException
from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import db
from pay_api.utils.errors import Error

_TOKEN_LEN = 21


class PaymentLinkService:
    """Create and consume opaque payment link tokens."""

    @staticmethod
    def _generate_token() -> str:
        return nanoid_generate(size=_TOKEN_LEN)

    @staticmethod
    def _build_url(token: str) -> str:
        base = current_app.config.get("PAY_NUXT_BASE_URL", "").rstrip("/")
        return f"{base}/{token}"

    @classmethod
    def attach_payment_link(cls, invoice_dto: dict) -> dict:
        """Persist a new link row for the invoice and merge `paymentUrl` into its DTO."""
        invoice_id = invoice_dto.get("id")
        if not invoice_id:
            return invoice_dto

        token = cls._generate_token()
        link = InvoicePaymentLinkModel(token=token, invoice_id=invoice_id)
        db.session.add(link)
        db.session.commit()

        invoice_dto["paymentUrl"] = cls._build_url(token)
        return invoice_dto

    @classmethod
    def resolve_token(cls, token: str, allow_linked: bool = False) -> InvoicePaymentLinkModel:
        """Return the link row iff it is usable for the caller's intent.

        Rejects unknown / invalidated / expired tokens unconditionally.
        Rejects already-consumed (`linked_at`) tokens unless `allow_linked=True`,
        which callers use for idempotent re-visits (same user returning with the
        same link — see `post_link_by_token`).

        Raises Error.INVALID_REQUEST (BusinessException) for any rejection.
        Callers surface it as a uniform response — do not distinguish failure
        modes to the client, to avoid enumeration signal.
        """
        link = InvoicePaymentLinkModel.find_by_token(token)
        if not link:
            raise BusinessException(Error.INVALID_REQUEST)
        if link.invalidated_at is not None:
            raise BusinessException(Error.INVALID_REQUEST)
        if not allow_linked and link.linked_at is not None:
            raise BusinessException(Error.INVALID_REQUEST)
        ttl_days = int(current_app.config.get("PAYMENT_LINK_TOKEN_TTL_DAYS", 30))
        if link.created_at < datetime.now(tz=UTC) - timedelta(days=ttl_days):
            raise BusinessException(Error.INVALID_REQUEST)
        return link

    @classmethod
    def resolve_active_token(cls, token: str) -> InvoicePaymentLinkModel:
        """Back-compat alias — first-time-link path (rejects consumed tokens)."""
        return cls.resolve_token(token, allow_linked=False)

    @classmethod
    def mark_linked(cls, link: InvoicePaymentLinkModel) -> None:
        """Set linked_at to now — future lookups treat the token as consumed."""
        link.linked_at = datetime.now(tz=UTC)
        db.session.add(link)
        db.session.commit()
