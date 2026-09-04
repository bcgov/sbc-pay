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
"""Service for opaque payment link tokens used by the express-checkout flow.

Tokens are nanoids (21 chars, URL-safe alphabet) stored in
`invoice_payment_links`. Knowing a token allows a user to view an invoice
summary, link it to their auth account, and pay it — but not to enumerate
other invoices or view any invoice they weren't given the token for.
"""

from datetime import UTC, datetime, timedelta

from flask import current_app
from nanoid import generate as nanoid_generate

from pay_api.exceptions import BusinessException
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import db
from pay_api.services.auth import check_auth
from pay_api.services.code import Code as CodeService
from pay_api.services.invoice import Invoice as InvoiceService
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.utils.constants import MAKE_PAYMENT
from pay_api.utils.enums import InvoiceStatus, PaymentMethod
from pay_api.utils.errors import Error
from pay_api.utils.user_context import UserContext, user_context
from pay_api.utils.util import get_str_by_path

_TOKEN_LEN = 21


class PaymentLinkService:
    """Create and consume opaque payment link tokens."""

    @staticmethod
    def _generate_token() -> str:
        return nanoid_generate(size=_TOKEN_LEN)

    @staticmethod
    def _build_url(token: str) -> str:
        base = current_app.config.get("EXPRESS_CHECKOUT_URL", "").rstrip("/")
        return f"{base}/pay/{token}"

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

        Rejects unknown / expired tokens unconditionally.
        Rejects already-consumed (`linked_at`) tokens unless `allow_linked=True`,
        which callers use for idempotent re-visits (same user returning with the
        same link — see `redeem`).

        TTL comes from the invoice's corp type (`payment_link_ttl_days`) with a
        fallback to the global `PAYMENT_LINK_TOKEN_TTL_DAYS` config.

        Raises Error.INVALID_REQUEST (BusinessException) for any rejection.
        Callers surface it as a uniform response — do not distinguish failure
        modes to the client, to avoid enumeration signal.
        """
        row = (
            db.session.query(InvoicePaymentLinkModel, InvoiceModel.corp_type_code)
            .join(InvoiceModel, InvoiceModel.id == InvoicePaymentLinkModel.invoice_id)
            .filter(InvoicePaymentLinkModel.token == token)
            .first()
        )
        if not row:
            raise BusinessException(Error.INVALID_REQUEST)
        link, corp_type_code = row
        if not allow_linked and link.linked_at is not None:
            raise BusinessException(Error.INVALID_REQUEST)

        ttl_days = CodeService.get_payment_link_ttl_days(corp_type_code)
        if link.created_at < datetime.now(tz=UTC) - timedelta(days=ttl_days):
            raise BusinessException(Error.INVALID_REQUEST)
        return link

    @classmethod
    def mark_linked(cls, link: InvoicePaymentLinkModel) -> None:
        """Set linked_at to now — future lookups treat the token as consumed."""
        link.linked_at = datetime.now(tz=UTC)
        db.session.add(link)
        db.session.commit()

    @classmethod
    def is_express_checkout_invoice(cls, invoice_id: int) -> bool:
        """Return True iff the invoice was created via the express-checkout flow.

        Presence of an `invoice_payment_links` row is the source of truth for
        express-checkout — corp-type flags only govern partner topic routing,
        not whether a given invoice actually went through the express-checkout path.
        """
        return db.session.query(InvoicePaymentLinkModel.token).filter_by(invoice_id=invoice_id).first() is not None

    @classmethod
    def stamp_partner_notified(cls, invoice_id: int) -> None:
        """Stamp partner_notified_at on the invoice's link row, if any.

        No-op for non-express-checkout invoices (no link row exists) and idempotent
        for already-notified rows. Called from every path that publishes a partner
        event so the link row records when the partner was told.
        """
        link = (
            db.session.query(InvoicePaymentLinkModel)
            .filter(InvoicePaymentLinkModel.invoice_id == invoice_id)
            .filter(InvoicePaymentLinkModel.partner_notified_at.is_(None))
            .first()
        )
        if link:
            link.partner_notified_at = datetime.now(tz=UTC)
            db.session.add(link)
            db.session.commit()

    @classmethod
    def find_invoice_by_token(cls, token: str) -> dict:
        """Return the invoice DTO for a valid payment link token.

        Used by the read-only GET /payment-links/{token} lookup so the pay-nuxt
        summary screen can render before the user has linked their account.

        Pre-redemption (`linked_at is None`) any caller may read the summary, signed in
        or not — the token is the credential. Once the link has been consumed,
        defer to Invoice._check_for_auth so only the account bound to the invoice
        can read it (auth-api round-trip spoof-proofs the Account-Id header).
        """
        link = cls.resolve_token(token, allow_linked=True)
        skip_auth = link.linked_at is None
        invoice = InvoiceService.find_by_id(link.invoice_id, skip_auth_check=skip_auth)
        return invoice.asdict(include_dynamic_fields=True)

    @classmethod
    @user_context
    def redeem(cls, token: str, **kwargs) -> dict:
        """Bind the invoice behind `token` to the caller's auth account and return its DTO.

        Account is taken from the Account-Id header via UserContext. This method calls
        check_auth itself to enforce MAKE_PAYMENT on the target account. Idempotent
        for the same account (re-visit returns current state); rejects if a different
        account tries to claim an already-linked invoice or the invoice has advanced
        past a linkable status.
        """
        user: UserContext = kwargs["user"]
        target_account_id = user.account_id
        if not target_account_id:
            raise BusinessException(Error.INVALID_REQUEST)

        # 403 if the user has no MAKE_PAYMENT authority on the target account.
        authorization = check_auth(
            business_identifier=None,
            account_id=target_account_id,
            contains_role=MAKE_PAYMENT,
        )

        link = cls.resolve_token(token, allow_linked=True)
        invoice = InvoiceService.find_by_id(link.invoice_id, skip_auth_check=True)

        target_account = PaymentAccountService.find_account(authorization)
        if not target_account:
            payment_method = (
                get_str_by_path(authorization, "account/paymentInfo/methodOfPayment") or PaymentMethod.DIRECT_PAY.value
            )
            target_account = PaymentAccountService.create(
                {
                    "accountId": target_account_id,
                    "paymentInfo": {"methodOfPayment": payment_method},
                }
            )

        if link.linked_at is not None:
            # Idempotent re-visit: same account gets the current state; different account is rejected.
            if invoice.payment_account_id != target_account.id:
                current_app.logger.info(
                    "payment link %s already bound to account %s but caller has %s",
                    link.token,
                    invoice.payment_account_id,
                    target_account.id,
                )
                raise BusinessException(Error.INVALID_REQUEST)
        else:
            # Express-checkout invoices are created as DIRECT_PAY / CREATED. Method switch
            # (to PAD/OB/etc.) can only happen after redemption, so any status other than
            # CREATED here means the invoice was tampered with or already moved on.
            if invoice.invoice_status_code != InvoiceStatus.CREATED.value:
                current_app.logger.info(
                    "payment link %s not linkable (invoice %s status=%s)",
                    link.token,
                    link.invoice_id,
                    invoice.invoice_status_code,
                )
                raise BusinessException(Error.INVALID_REQUEST)

            invoice.payment_account_id = target_account.id
            invoice.cfs_account_id = target_account.cfs_account_id
            invoice.save()
            cls.mark_linked(link)

        return InvoiceService.find_by_id(link.invoice_id, skip_auth_check=True).asdict(include_dynamic_fields=True)
