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
"""Abstract class for payment system implementation."""

import functools
import traceback
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import current_app
from sbc_common_components.utils.enums import QueueMessageTypes
from sentry_sdk import capture_message

from pay_api.exceptions import BusinessException
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Credit as CreditModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models.refunds_partial import RefundPartialLine
from pay_api.services import gcp_queue_publisher
from pay_api.services.auth import get_account_admin_users
from pay_api.services.cfs_service import CFSService
from pay_api.services.email_service import _render_credit_add_notification_template, send_email
from pay_api.services.flags import flags
from pay_api.services.invoice import Invoice
from pay_api.services.invoice_reference import InvoiceReference
from pay_api.services.payment import Payment
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.enums import (
    CorpType,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    QueueSources,
    RefundsPartialType,
    TransactionStatus,
)
from pay_api.utils.errors import Error
from pay_api.utils.util import get_local_formatted_date_time, get_topic_for_corp_type

from .payment_line_item import PaymentLineItem
from .receipt import Receipt


class PaymentSystemService(ABC):  # pylint: disable=too-many-instance-attributes
    """Abstract base class for payment system.

    This class will list the operations implemented for any payment system.
    Any payment system service SHOULD implement this class and implement the abstract methods.
    """

    def __init__(self):  # pylint:disable=useless-super-delegation
        """Initialize."""
        super(PaymentSystemService, self).__init__()  # pylint:disable=super-with-arguments

    def create_account(
        self,
        identifier: str,
        contact_info: Dict[str, Any],
        payment_info: Dict[str, Any],
        **kwargs,
    ) -> CfsAccountModel:
        # pylint: disable=unused-argument
        """Create account in payment system."""
        return None

    def update_account(
        self,
        name: str,
        cfs_account: CfsAccountModel,  # pylint: disable=unused-argument
        payment_info: Dict[str, Any],
    ) -> CfsAccountModel:  # pylint: disable=unused-argument
        """Update account in payment system."""
        return None

    @abstractmethod
    def create_invoice(
        self,
        payment_account: PaymentAccount,
        line_items: List[PaymentLineItem],
        invoice: Invoice,
        **kwargs,
    ) -> InvoiceReference:
        """Create invoice in payment system."""

    def update_invoice(  # pylint:disable=too-many-arguments,unused-argument
        self,
        payment_account: PaymentAccount,  # pylint: disable=unused-argument
        line_items: List[PaymentLineItem],
        invoice_id: int,  # pylint: disable=unused-argument
        paybc_inv_number: str,
        reference_count: int = 0,  # pylint: disable=unused-argument
        **kwargs,
    ):
        """Update invoice in payment system."""
        return None

    def cancel_invoice(
        self,
        payment_account: PaymentAccount,  # pylint:disable=unused-argument
        inv_number: str,
    ):  # pylint: disable=unused-argument
        """Cancel invoice in payment system."""
        return None

    def get_receipt(
        self,
        payment_account: PaymentAccount,  # pylint:disable=unused-argument
        pay_response_url: str,
        invoice_reference: InvoiceReference,
    ):  # pylint: disable=unused-argument
        """Get receipt from payment system."""
        return None

    def get_payment_system_url_for_invoice(
        self,
        invoice: Invoice,  # pylint:disable=unused-argument
        inv_ref: InvoiceReference,  # pylint: disable=unused-argument
        return_url: str,
    ) -> str:  # pylint: disable=unused-argument
        """Return the payment system portal URL for payment."""
        return None

    def get_payment_system_url_for_payment(
        self,
        payment: Payment,  # pylint:disable=unused-argument
        inv_ref: InvoiceReference,  # pylint: disable=unused-argument
        return_url: str,
    ) -> str:  # pylint: disable=unused-argument
        """Return the payment system portal URL for payment."""
        return None

    def process_cfs_refund(
        self,
        invoice: InvoiceModel,  # pylint:disable=unused-argument
        payment_account: PaymentAccount,  # pylint:disable=unused-argument
        refund_partial: List[RefundPartialLine],
    ):  # pylint:disable=unused-argument
        """Process Refund if any."""
        return None

    def get_pay_system_reason_code(self, pay_response_url: str) -> str:  # pylint:disable=unused-argument
        """Return the Pay system reason code."""
        return None

    @abstractmethod
    def get_payment_system_code(self):
        """Return the payment system code. E.g, PAYBC, BCOL etc."""

    @abstractmethod
    def get_payment_method_code(self):
        """Return the payment method code. E.g, CC, DRAWDOWN etc."""

    def get_default_invoice_status(self) -> str:
        """Return the default status for invoice when created."""
        return InvoiceStatus.CREATED.value

    def get_default_payment_status(self) -> str:
        """Return the default status for payment when created."""
        return PaymentStatus.CREATED.value

    def complete_post_invoice(
        self,
        invoice: Invoice,  # pylint: disable=unused-argument
        invoice_reference: InvoiceReference,
    ) -> None:  # pylint: disable=unused-argument
        """Complete any post invoice activities if needed."""
        return None

    def apply_credit(self, invoice: Invoice) -> None:  # pylint:disable=unused-argument
        """Apply credit on invoice."""
        return None

    def ensure_no_payment_blockers(self, payment_account: PaymentAccount) -> None:  # pylint: disable=unused-argument
        """Ensure no payment blockers are present."""
        if payment_account.has_nsf_invoices:
            # Note NSF (Account Unlocking) is paid using DIRECT_PAY - CC flow, not PAD.
            current_app.logger.warning(f"Account {payment_account.id} is frozen, rejecting invoice creation")
            raise BusinessException(Error.PAD_CURRENTLY_NSF)
        if payment_account.has_overdue_invoices:
            raise BusinessException(Error.EFT_INVOICES_OVERDUE)

    @staticmethod
    def release_payment_or_reversal(invoice: Invoice, transaction_status=TransactionStatus.COMPLETED.value):
        """Release record."""
        from .payment_transaction import PaymentTransaction  # pylint:disable=import-outside-toplevel,cyclic-import

        if invoice.corp_type_code in [
            CorpType.CSO.value,
            CorpType.RPT.value,
            CorpType.VS.value,
        ]:
            return

        if transaction_status == TransactionStatus.REVERSED.value and not flags.is_on(
            "queue-message-for-reversals", default=False
        ):
            return

        payload = PaymentTransaction.create_event_payload(invoice, transaction_status)
        try:
            current_app.logger.info(f"Releasing record for invoice {invoice.id} with status {transaction_status}")
            gcp_queue_publisher.publish_to_queue(
                gcp_queue_publisher.QueueMessage(
                    source=QueueSources.PAY_API.value,
                    message_type=QueueMessageTypes.PAYMENT.value,
                    payload=payload,
                    topic=get_topic_for_corp_type(invoice.corp_type_code),
                    corp_type=invoice.corp_type_code,
                )
            )
        except Exception as e:  # NOQA pylint: disable=broad-except
            current_app.logger.error(f"{{error: {str(e)}, stack_trace: {traceback.format_exc()}}}")
            current_app.logger.error("Notification to Queue failed for the Payment Event %s", payload)
            capture_message(
                f"Notification to Queue failed for the Payment Event : {payload}.",
                level="error",
            )

    @staticmethod
    def validate_refund_amount(refund_amount, max_amount):
        """Validate refund amount."""
        if refund_amount > max_amount:
            current_app.logger.error(
                f"Refund amount {str(refund_amount)} " f"exceeds maximum allowed amount {str(max_amount)}."
            )
            raise BusinessException(Error.INVALID_REQUEST)

    @staticmethod
    def _refund_and_create_credit_memo(invoice: InvoiceModel, refund_partial: List[RefundPartialLine] = None):
        # Create credit memo in CFS if the invoice status is PAID.
        # Don't do anything is the status is APPROVED.
        is_partial = bool(refund_partial)

        current_app.logger.info(f"Creating credit memo for invoice : {invoice.id}, {invoice.invoice_status_code}")

        if is_partial and invoice.invoice_status_code != InvoiceStatus.PAID.value:
            raise BusinessException(Error.PARTIAL_REFUND_INVOICE_NOT_PAID)

        if (
            invoice.invoice_status_code == InvoiceStatus.APPROVED.value
            and InvoiceReferenceModel.find_by_invoice_id_and_status(invoice.id, InvoiceReferenceStatus.ACTIVE.value)
            is None
        ):
            return InvoiceStatus.CANCELLED.value

        cfs_account = CfsAccountModel.find_effective_or_latest_by_payment_method(
            invoice.payment_account_id, invoice.payment_method_code
        )

        line_items: List[PaymentLineItemModel] = []
        refund_amount = 0

        if is_partial:
            for refund_line in refund_partial:
                pli = PaymentLineItemModel.find_by_id(refund_line.payment_line_item_id)
                if not pli or refund_line.refund_amount < 0:
                    raise BusinessException(Error.INVALID_REQUEST)
                max_refundable = (
                    pli.service_fees if refund_line.refund_type == RefundsPartialType.SERVICE_FEES.value else pli.total
                )
                PaymentSystemService.validate_refund_amount(refund_line.refund_amount, max_refundable)
                line_items.append(pli)
                refund_amount += refund_line.refund_amount
        else:
            line_items = [PaymentLineItemModel.find_by_id(li.id) for li in invoice.payment_line_items]
            refund_amount = invoice.total

        cms_response = CFSService.create_cms(line_items=line_items, cfs_account=cfs_account)
        # TODO Create a payment record for this to show up on transactions, when the ticket comes.
        # Create a credit with CM identifier as CMs are not reported in payment interface file
        # until invoice is applied.
        CreditModel(
            cfs_identifier=cms_response.get("credit_memo_number"),
            is_credit_memo=True,
            amount=refund_amount,
            remaining_amount=refund_amount,
            account_id=invoice.payment_account_id,
        ).flush()

        # Add up the credit amount and update payment account table.
        payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(invoice.payment_account_id)
        payment_account.credit = (payment_account.credit or 0) + refund_amount
        current_app.logger.info(
            f"Updating credit amount to {payment_account.credit} for account {payment_account.auth_account_id}"
        )
        payment_account.flush()

        PaymentSystemService._send_credit_notification(payment_account, refund_amount)

        if is_partial and refund_amount != invoice.total:
            return InvoiceStatus.PAID.value

        return InvoiceStatus.CREDITED.value

    @staticmethod
    def _send_credit_notification(payment_account: PaymentAccountModel, refund_amount: float):
        """Send credit notification email to account admins."""
        receiver_recipients = []
        org_admins_response = get_account_admin_users(payment_account.auth_account_id)

        members = org_admins_response.get("members") if org_admins_response.get("members", None) else []
        for member in members:
            if (user := member.get("user")) and (contacts := user.get("contacts")):
                receiver_recipients.append(contacts[0].get("email"))

        subject = f"${refund_amount} {'credits' if refund_amount > 1 else 'credit'} was added to your account "
        html_body = _render_credit_add_notification_template(
            {
                "amount": refund_amount,
                "account_number": payment_account.auth_account_id,
                "account_name_with_branch": (
                    f"{payment_account.name}-{payment_account.branch_name}"
                    if payment_account.branch_name and payment_account.branch_name not in payment_account.name
                    else payment_account.name
                ),
                "login_url": (f"{current_app.config.get('AUTH_WEB_URL')}/account/"
                              f"{payment_account.auth_account_id}/settings/transactions"),
            }
        )
        send_email(receiver_recipients, subject, html_body)

    @staticmethod
    def _publish_refund_to_mailer(invoice: InvoiceModel):
        """Construct message and send to mailer queue."""
        receipt: ReceiptModel = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice_id=invoice.id)
        invoice_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
            invoice_id=invoice.id,
            status_code=InvoiceReferenceStatus.COMPLETED.value,
        )
        payment_transaction: PaymentTransactionModel = PaymentTransactionModel.find_recent_completed_by_invoice_id(
            invoice_id=invoice.id
        )
        transaction_date_time = (
            receipt.receipt_date
            if invoice.payment_method_code == PaymentMethod.DRAWDOWN.value
            else payment_transaction.transaction_end_time
        )
        filing_description = ""
        for line_item in invoice.payment_line_items:
            if filing_description:
                filing_description += ","
            filing_description += line_item.description

        payload = {
            "identifier": invoice.business_identifier,
            "orderNumber": receipt.receipt_number,
            "transactionDateTime": get_local_formatted_date_time(transaction_date_time),
            "transactionAmount": receipt.receipt_amount,
            "transactionId": invoice_ref.invoice_number,
            "refundDate": get_local_formatted_date_time(datetime.now(tz=timezone.utc), "%Y%m%d"),
            "filingDescription": filing_description,
        }
        if invoice.payment_method_code == PaymentMethod.DRAWDOWN.value:
            payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(invoice.payment_account_id)
            filing_description += ","
            filing_description += invoice_ref.invoice_number
            payload.update(
                {
                    "bcolAccount": invoice.bcol_account,
                    "bcolUser": payment_account.bcol_user_id,
                    "filingDescription": filing_description,
                }
            )
        current_app.logger.debug(f"Publishing payment refund request to mailer for {invoice.id} : {payload}")
        gcp_queue_publisher.publish_to_queue(
            gcp_queue_publisher.QueueMessage(
                source=QueueSources.PAY_API.value,
                message_type=QueueMessageTypes.REFUND_DRAWDOWN_REQUEST.value,
                payload=payload,
                topic=current_app.config.get("ACCOUNT_MAILER_TOPIC"),
            )
        )

    def complete_payment(self, invoice, invoice_reference):
        """Create payment and related records as if the payment is complete."""
        Payment.create(
            payment_method=self.get_payment_method_code(),
            payment_system=self.get_payment_system_code(),
            payment_status=PaymentStatus.COMPLETED.value,
            invoice_number=invoice_reference.invoice_number,
            invoice_amount=invoice.total,
            payment_account_id=invoice.payment_account_id,
        )
        invoice.invoice_status_code = InvoiceStatus.PAID.value
        invoice.paid = invoice.total
        current_time = datetime.now(tz=timezone.utc)
        invoice.payment_date = current_time
        invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value
        # Create receipt.
        receipt = Receipt()
        receipt.receipt_number = invoice_reference.invoice_number
        receipt.receipt_amount = invoice.total
        receipt.invoice_id = invoice.id
        receipt.receipt_date = current_time
        receipt.save()


def skip_invoice_for_sandbox(function):
    """Skip downstream system (BCOL, CFS) if the invoice creation is in sandbox environment."""

    @functools.wraps(function)
    def wrapper(*func_args, **func_kwargs):
        """Complete any post invoice activities if needed."""
        if current_app.config.get("ENVIRONMENT_NAME") == "sandbox":
            current_app.logger.info("Skipping invoice creation as sandbox environment is detected.")
            invoice: Invoice = func_args[3]  # 3 is invoice from the create_invoice signature
            return InvoiceReference.create(invoice.id, f"SANDBOX-{invoice.id}", f"REF-{invoice.id}")
        return function(*func_args, **func_kwargs)

    return wrapper


def skip_complete_post_invoice_for_sandbox(function):
    """Skip actual implementation invocation and mark all records as complete if it's sandbox."""

    @functools.wraps(function)
    def wrapper(*func_args, **func_kwargs):
        """Complete any post invoice activities."""
        if current_app.config.get("ENVIRONMENT_NAME") == "sandbox":
            current_app.logger.info("Completing the payment as sandbox environment is detected.")
            instance: PaymentSystemService = func_args[0]
            instance.complete_payment(func_args[1], func_args[2])  # invoice and invoice ref
            instance.release_payment_or_reversal(func_args[1])
            return None
        return function(*func_args, **func_kwargs)

    return wrapper
