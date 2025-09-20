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

from datetime import datetime, timezone
from typing import Dict, List

from flask import current_app
from requests.exceptions import HTTPError

from pay_api.exceptions import BusinessException, Error
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models.corp_type import CorpType
from pay_api.models.invoice_reference import InvoiceReference as InvoiceReferenceModel
from pay_api.models.refunds_partial import RefundPartialLine
from pay_api.utils.enums import AuthHeaderType, ContentType, PaymentMethod, PaymentStatus
from pay_api.utils.enums import PaymentSystem as PaySystemCode
from pay_api.utils.errors import get_bcol_error
from pay_api.utils.user_context import UserContext, user_context
from pay_api.utils.util import generate_transaction_number

from .base_payment_system import PaymentSystemService, skip_complete_post_invoice_for_sandbox, skip_invoice_for_sandbox
from .invoice import Invoice
from .invoice_reference import InvoiceReference
from .oauth_service import OAuthService
from .payment_account import PaymentAccount
from .payment_line_item import PaymentLineItem


class BcolService(PaymentSystemService, OAuthService):
    """Service to manage BCOL integration."""

    def get_payment_system_code(self):
        """Return PAYBC as the system code."""
        return PaySystemCode.BCOL.value

    @user_context
    @skip_invoice_for_sandbox
    def create_invoice(  # pylint: disable=too-many-locals
        self,
        payment_account: PaymentAccount,
        line_items: List[PaymentLineItem],
        invoice: Invoice,
        **kwargs,
    ) -> InvoiceReferenceModel:
        """Create Invoice in PayBC."""
        self.ensure_no_payment_blockers(payment_account)
        current_app.logger.debug(
            f"<Creating BCOL records for Invoice: {invoice.id}, " f"Auth Account : {payment_account.auth_account_id}"
        )
        user: UserContext = kwargs["user"]
        force_non_staff_fee_code = "force_non_staff_fee_code" in kwargs
        pay_endpoint = current_app.config.get("BCOL_API_ENDPOINT") + "payments"
        invoice_number = generate_transaction_number(invoice.id)
        corp_number = invoice.business_identifier or ""
        amount_excluding_txn_fees = sum(line.total for line in line_items)
        if invoice.service_fees > 1.5:
            current_app.logger.error(
                f"Service fees ${invoice.service_fees} greater than $1.50 detected,"
                " BCONLINE only charges up to a max of $1.50 for a service fee."
            )
        filing_types = ",".join([item.fee_schedule.filing_type_code for item in line_items])
        remarks = f"{corp_number}({filing_types})"
        if user.first_name:
            remarks = f"{remarks}-{user.first_name}"

        use_staff_fee_code = user.is_staff() or user.is_system()
        force_use_debit_account = False
        # CSO currently refunds an invoice, and creates a new invoice for partial refunds.
        # Only applies for CSBPDOC. CSO only uses a single PLI per invoice.
        # This allows service fees to be charged via service account.
        if filing_types == "CSBPDOC" or force_non_staff_fee_code:
            use_staff_fee_code = False
            force_use_debit_account = True
        payload: Dict = {
            "userId": payment_account.bcol_user_id,
            "invoiceNumber": invoice_number,
            "folioNumber": invoice.folio_number,
            "amount": str(amount_excluding_txn_fees),
            "rate": str(amount_excluding_txn_fees),
            "remarks": remarks[:50],
            "feeCode": self._get_fee_code(invoice.service_fees, invoice.corp_type_code, use_staff_fee_code),
            "forceUseDebitAccount": force_use_debit_account,
            "serviceFees": str(invoice.service_fees),
        }
        if use_staff_fee_code:
            payload["userId"] = (
                user.user_name_with_no_idp
                if user.is_staff()
                else current_app.config["BCOL_USERNAME_FOR_SERVICE_ACCOUNT_PAYMENTS"]
            )
            payload["accountNumber"] = invoice.bcol_account
            payload["formNumber"] = invoice.dat_number or ""
            payload["reduntantFlag"] = "Y"
            payload["rateType"] = "C"

        if payload.get("folioNumber", None) is None:  # Set empty folio if None
            payload["folioNumber"] = ""
        try:
            pay_response = self.post(
                pay_endpoint,
                user.bearer_token,
                AuthHeaderType.BEARER,
                ContentType.JSON,
                payload,
                raise_for_error=False,
            )
            response_json = pay_response.json()
            current_app.logger.debug(f"BCOL Response : {response_json}")
            pay_response.raise_for_status()
        except HTTPError as bol_err:
            self._handle_http_error(bol_err, response_json, payload)
        invoice_reference = InvoiceReference.create(
            invoice.id, response_json.get("key"), response_json.get("sequenceNo")
        )
        return invoice_reference

    def _handle_http_error(self, bol_err, response_json, payload):
        """Log BCOL errors."""
        error_type: str = response_json.get("type")
        # It's possible raise_for_status, skips this part.
        if error_type and error_type.isdigit():
            error = get_bcol_error(int(error_type))
            if error in [Error.BCOL_ERROR, Error.BCOL_UNAVAILABLE]:
                current_app.logger.error(bol_err)
            else:
                # The other BCOL errors are related to BCOL account.
                current_app.logger.warning(bol_err)
        else:
            error = Error.BCOL_ERROR
            current_app.logger.error(bol_err)
            current_app.logger.error(f"Request {payload} - Response: {response_json}")
        raise BusinessException(error) from bol_err

    def get_receipt(
        self,
        payment_account: PaymentAccount,
        pay_response_url: str,
        invoice_reference: InvoiceReference,
    ):
        """Get receipt from bcol for the receipt number or get receipt against invoice number."""
        current_app.logger.debug("<get_receipt")
        invoice = Invoice.find_by_id(invoice_reference.invoice_id, skip_auth_check=True)
        return (
            f"{invoice_reference.invoice_number}",
            datetime.now(tz=timezone.utc),
            invoice.total,
        )

    def _get_fee_code(self, service_fees: float, corp_type: str, is_staff: bool = False):
        """Return BCOL fee code."""
        corp_type = CorpType.find_by_code(code=corp_type)
        service_fees = float(service_fees)
        if is_staff:
            return corp_type.bcol_staff_fee_code
        if service_fees in (1.5, 1.05):
            return corp_type.bcol_code_full_service_fee
        if service_fees == 1:
            return corp_type.bcol_code_partial_service_fee
        if service_fees == 0:
            return corp_type.bcol_code_no_service_fee
        current_app.logger.error(f"Service fees ${service_fees}, defaulting to full_service_fee.")
        return corp_type.bcol_code_full_service_fee

    def get_payment_method_code(self):
        """Return CC as the method code."""
        return PaymentMethod.DRAWDOWN.value

    def process_cfs_refund(
        self,
        invoice: InvoiceModel,
        payment_account: PaymentAccount,
        refund_partial: List[RefundPartialLine],
    ):  # pylint:disable=unused-argument
        """Process refund in CFS."""
        self._publish_refund_to_mailer(invoice)
        payment = PaymentModel.find_payment_for_invoice(invoice.id)
        payment.payment_status_code = PaymentStatus.REFUNDED.value
        payment.flush()

    @user_context
    @skip_complete_post_invoice_for_sandbox
    def complete_post_invoice(
        self,
        invoice: Invoice,  # pylint: disable=unused-argument
        invoice_reference: InvoiceReference,
        **kwargs,
    ) -> None:
        """Complete any post payment activities if needed."""
        self.complete_payment(invoice, invoice_reference)
        # Publish message to the queue with payment token, so that they can release records on their side.
        self.release_payment_or_reversal(invoice=invoice)
