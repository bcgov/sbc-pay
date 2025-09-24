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
"""Service to manage PayBC interaction."""

import urllib.parse
from decimal import Decimal
from typing import Any

from dateutil import parser
from flask import current_app

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import RefundPartialLine
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.cfs_service import CFSService
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment import Payment
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import AuthHeaderType, CfsAccountStatus, ContentType, PaymentMethod, PaymentSystem
from pay_api.utils.util import parse_url_params

from .payment_line_item import PaymentLineItem


class PaybcService(PaymentSystemService, CFSService):
    """Service to manage PayBC integration. - for NSF/balance payments, we usually use direct pay service instead."""

    def get_payment_system_url_for_invoice(self, invoice: Invoice, inv_ref: InvoiceReference, return_url: str):  # noqa: ARG002
        """Return the payment system url."""
        current_app.logger.debug("<get_payment_system_url")
        pay_system_url = self._build_payment_url(inv_ref, return_url)

        current_app.logger.debug(">get_payment_system_url")
        return pay_system_url

    def get_payment_system_code(self):
        """Return PAYBC as the system code."""
        return PaymentSystem.PAYBC.value

    def get_payment_method_code(self):
        """Return CC as the method code."""
        return PaymentMethod.CC.value

    def create_account(
        self,
        identifier: str,  # noqa: ARG002
        contact_info: dict[str, Any],
        payment_info: dict[str, Any],  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ) -> any:
        """Create account in PayBC."""
        cfs_account = CfsAccountModel()
        cfs_account_details = self.create_cfs_account(identifier, contact_info, receipt_method=None)
        # Update model with response values
        cfs_account.cfs_account = cfs_account_details.get("account_number")
        cfs_account.cfs_site = cfs_account_details.get("site_number")
        cfs_account.cfs_party = cfs_account_details.get("party_number")
        cfs_account.status = CfsAccountStatus.ACTIVE.value
        cfs_account.payment_method = PaymentMethod.CC.value
        return cfs_account

    def create_invoice(
        self,
        payment_account: PaymentAccount,  # pylint: disable=too-many-locals
        line_items: list[PaymentLineItem],  # noqa: ARG002
        invoice: Invoice,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ) -> InvoiceReference:
        """Create Invoice in PayBC."""
        # Build line item model array, as that's needed for CFS Service
        # No need to check for payment blockers here as this payment method is used to unblock.
        line_item_models: list[PaymentLineItemModel] = []
        for line_item in line_items:
            line_item_models.append(PaymentLineItemModel.find_by_id(line_item.id))

        invoice_response = self.create_account_invoice(invoice.id, line_item_models, payment_account)

        invoice_reference: InvoiceReference = InvoiceReference.create(
            invoice.id,
            invoice_response.get("invoice_number", None),
            invoice_response.get("pbc_ref_number", None),
        )

        return invoice_reference

    def update_invoice(  # pylint: disable=too-many-arguments
        self,
        payment_account: PaymentAccount,  # noqa: ARG002
        line_items: list[PaymentLineItem],  # noqa: ARG002
        invoice_id: int,  # noqa: ARG002
        paybc_inv_number: str,  # noqa: ARG002
        reference_count: int = 0,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ):
        """Update the invoice.

        1. Adjust the existing invoice to zero
        2. Create a new invoice
        """
        self.reverse_invoice(paybc_inv_number)
        return self.create_invoice(
            payment_account=payment_account,
            line_items=line_items,
            invoice=None,
            corp_type_code=kwargs.get("corp_type_code"),
            invoice_number=f"{invoice_id}-{reference_count}",
        )

    def cancel_invoice(self, payment_account: PaymentAccount, inv_number: str):
        """Adjust the invoice to zero."""
        current_app.logger.debug("<cancel_invoice %s, %s", payment_account, inv_number)
        self.reverse_invoice(inv_number)

    def get_receipt(
        self,
        payment_account: PaymentAccount,  # noqa: ARG002
        pay_response_url: str,  # noqa: ARG002
        invoice_reference: InvoiceReference,  # noqa: ARG002
    ):
        """Get receipt from paybc for the receipt number or get receipt against invoice number."""
        current_app.logger.debug("<paybc_service_Getting token")
        current_app.logger.debug("<Getting receipt")
        receipt_url = (
            current_app.config.get("CFS_BASE_URL") + f"/cfs/parties/{payment_account.cfs_party}/accs/"
            f"{payment_account.cfs_account}/sites/{payment_account.cfs_site}/rcpts/"
        )
        parsed_url = parse_url_params(pay_response_url)
        receipt_number: str = parsed_url.get("receipt_number") if "receipt_number" in parsed_url else None
        if not receipt_number:
            invoice = InvoiceModel.find_by_id(invoice_reference.invoice_id)
            cfs_account = CfsAccountModel.find_by_id(invoice.cfs_account_id)
            invoice = self.get_invoice(cfs_account, invoice_reference.invoice_number)
            for receipt in invoice.get("receipts", []):
                receipt_applied_links = [
                    link for link in receipt.get("links", []) if link.get("rel") == "receipt_applied"
                ]
                if receipt_applied_links:
                    # Takes the top, there could definitely be multiple, will have to tackle this in the future.
                    href = receipt_applied_links[0].get("href")
                    if href:
                        receipt_number = href.rstrip("/").split("/")[-1]
                        break
        if receipt_number:
            receipt_response = self._get_receipt_by_number(
                CFSService.get_token().json().get("access_token"), receipt_url, receipt_number
            )
            receipt_date = parser.parse(receipt_response.get("receipt_date"))

            amount = Decimal("0")
            for invoice in receipt_response.get("invoices"):
                if invoice.get("invoice_number") == invoice_reference.invoice_number:
                    amount += Decimal(invoice.get("amount_applied"))

            return receipt_number, receipt_date, float(amount)
        return None

    def _get_receipt_by_number(
        self,
        access_token: str = None,  # noqa: ARG002
        receipt_url: str = None,  # noqa: ARG002
        receipt_number: str = None,  # noqa: ARG002
    ):
        """Get receipt details by receipt number."""
        if receipt_number:
            receipt_url = receipt_url + f"{receipt_number}/"
        return self.get(
            receipt_url,
            access_token,
            AuthHeaderType.BEARER,
            ContentType.JSON,
            True,
            additional_headers={"Pay-Connector": current_app.config.get("PAY_CONNECTOR_AUTH")},
        ).json()

    def process_cfs_refund(
        self,
        invoice: InvoiceModel,  # noqa: ARG002
        payment_account: PaymentAccount,  # noqa: ARG002
        refund_partial: list[RefundPartialLine],  # noqa: ARG002
    ):  # pylint:disable=unused-argument
        """Process refund in CFS."""
        return super()._refund_and_create_credit_memo(invoice)

    def get_payment_system_url_for_payment(self, payment: Payment, inv_ref: InvoiceReference, return_url: str):
        """Return the payment system url."""
        current_app.logger.debug(
            "<get_payment_system_url_for_payment ID: %s, Inv Number: %s",  # noqa: ARG002
            payment.id,
            payment.invoice_number,
        )
        pay_system_url = self._build_payment_url(inv_ref, return_url)
        current_app.logger.debug(">get_payment_system_url_for_payment")
        return pay_system_url

    @staticmethod
    def _build_payment_url(inv_ref, return_url):
        paybc_url = current_app.config.get("PAYBC_PORTAL_URL")
        pay_system_url = f"{paybc_url}?inv_number={inv_ref.invoice_number}&pbc_ref_number={inv_ref.reference_number}"
        encoded_return_url = urllib.parse.quote(return_url, "")
        pay_system_url += f"&redirect_uri={encoded_return_url}"
        return pay_system_url


def get_non_null_value(value: str, default_value: str):
    """Return non null value for the value by replacing default value."""
    return default_value if (value is None or value.strip() == "") else value
