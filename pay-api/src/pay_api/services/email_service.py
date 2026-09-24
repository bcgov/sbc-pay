# Copyright © 2024 Province of British Columbia
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

"""This manages all of the email notification service."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from attrs import define
from flask import copy_current_request_context, current_app, has_request_context
from jinja2 import Environment, FileSystemLoader
from sbc_common_components.utils.enums import QueueMessageTypes

from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.services import gcp_queue_publisher
from pay_api.services.auth import get_service_account_token
from pay_api.services.oauth_service import OAuthService
from pay_api.services.receipt import Receipt as ReceiptService
from pay_api.utils.enums import AuthHeaderType, ContentType, InvoiceReferenceStatus, QueueSources, RefundStatus
from pay_api.utils.json_util import DecimalEncoder
from pay_api.utils.serializable import Serializable
from pay_api.utils.util import get_local_formatted_date

_executor = ThreadPoolExecutor(max_workers=5)


def send_email(recipients: list[str], subject: str, body: str):
    """Send the email notification."""
    # Note if we send HTML in the body, we aren't sending through GCNotify,
    # ideally we'd like to send through GCNotify.
    token = get_service_account_token()
    current_app.logger.info(f">send_email to recipients: {recipients}")
    notify_url = current_app.config.get("NOTIFY_API_ENDPOINT") + "notify/"

    success = False

    for recipient in recipients:
        notify_body = {
            "recipients": recipient,
            "content": {"subject": subject, "body": body},
        }

        try:
            notify_response = OAuthService.post(
                notify_url,
                token=token,
                auth_header_type=AuthHeaderType.BEARER,
                content_type=ContentType.JSON,
                data=notify_body,
            )
            current_app.logger.info("<send_email notify_response")
            if notify_response:
                current_app.logger.info(f"Successfully sent email to {recipient}")
                success = True
        except Exception as e:  # NOQA pylint:disable=broad-except
            current_app.logger.error(f"Error sending email to {recipient}: {e}")

    return success


def send_email_async(recipients: list[str], subject: str, body: str):
    """Send the email notification asynchronously using ThreadExecutor.

    Args:
        recipients: List of email recipients
        subject: Email subject
        body: Email body

    Returns:
        Future object representing the asynchronous email sending task
    """
    app = current_app._get_current_object()

    def _send_email_task(recipients_list, email_subject, email_body):
        """Send the email notification in background thread."""
        if has_request_context():

            @copy_current_request_context
            def _inner():
                return send_email(recipients_list, email_subject, email_body)
        else:

            def _inner():
                with app.app_context():
                    return send_email(recipients_list, email_subject, email_body)

        return _inner()

    return _executor.submit(_send_email_task, recipients, subject, body)


@define
class ShortNameRefundEmailContent(Serializable):
    """Short name refund email."""

    comment: str
    decline_reason: str
    refund_amount: Decimal
    refund_method: str
    short_name_id: int
    short_name: str
    status: str
    url: str

    def render_body(self, is_for_client=False) -> str:
        """Render the email body using the provided template."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root_dir = os.path.dirname(current_dir)
        templates_dir = os.path.join(project_root_dir, "templates")
        env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)
        if is_for_client:
            template = env.get_template("eft_refund_notification_client.html")
        else:
            template = env.get_template("eft_refund_notification_staff.html")
        return template.render(self.to_dict())


def _render_payment_reversed_template(params: dict) -> str:
    """Render short name statement reverse payment template."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(current_dir)
    templates_dir = os.path.join(project_root_dir, "templates")
    env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)
    template = env.get_template("eft_reverse_payment.html")

    account_id = params["accountId"]
    statement_url = f"{current_app.config.get('AUTH_WEB_URL')}/account/{account_id}/settings/statements"
    params["statementUrl"] = statement_url

    return template.render(params)


def _render_credit_add_notification_template(params: dict) -> str:
    """Render credit add notification template."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(current_dir)
    templates_dir = os.path.join(project_root_dir, "templates")
    env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)
    template = env.get_template("credit_add_notification.html")
    return template.render(params)


def _receipt_template_vars(invoice) -> dict | None:
    """Return the report-api vars for the receipt PDF, or None when there is no receipt yet."""
    try:
        filing_data = {"filingDateTime": get_local_formatted_date(invoice.created_on)}
        # pay-queue calls this too, and url_for can't build `_links` there.
        details = ReceiptService.get_receipt_details(filing_data, invoice.id, skip_auth_check=True, include_links=False)
        # The queue encodes with plain json, which can't take the Decimals in here.
        return json.loads(json.dumps({**details, **filing_data}, cls=DecimalEncoder))
    except Exception:  # NOQA # pylint: disable=broad-except
        current_app.logger.exception("Could not build the receipt vars for invoice %s", invoice.id)
        return None


def send_receipt_notification(invoice):
    """Ask account-mailer to email the receipt after a payment settles.

    Called from both pay-api and pay-queue — card payments settle on the PayBC return,
    OB and PAD later in reconciliation. Only database reads happen here; the recipient
    lookup, PDF render and send run in account-mailer.

    An express-checkout invoice whose link nobody claimed has no account, so it goes to the
    address the partner supplied at invoice creation. Without that address there is nobody
    to tell.

    Failures are logged and never affect the payment.
    """
    try:
        payment_account = PaymentAccountModel.find_by_id(invoice.payment_account_id)
        if not payment_account:
            current_app.logger.info("No payment account found for invoice %s", invoice.id)
            return
        unredeemed_link = InvoicePaymentLinkModel.find_unredeemed_for_invoice(invoice.id)
        if unredeemed_link:
            if not unredeemed_link.email:
                current_app.logger.info("No one to send the receipt for invoice %s to; skipping.", invoice.id)
                return
            recipient = {"emailAddresses": unredeemed_link.email}
        elif payment_account.auth_account_id:
            recipient = {"accountId": payment_account.auth_account_id}
        else:
            return

        invoice_reference = InvoiceReferenceModel.find_by_invoice_id_and_status(
            invoice.id, InvoiceReferenceStatus.COMPLETED.value
        )
        # Must read the same as the fee summary, so use its line-item descriptions.
        transaction_detail = ", ".join(
            line.description for line in (invoice.payment_line_items or []) if line.description
        )
        gcp_queue_publisher.publish_to_queue(
            gcp_queue_publisher.QueueMessage(
                source=QueueSources.PAY_API.value,
                message_type=QueueMessageTypes.PAYMENT_RECEIPT.value,
                payload={
                    **recipient,
                    "invoiceId": invoice.id,
                    "amount": f"{float(invoice.total):.2f}",
                    "invoiceNumber": invoice_reference.invoice_number if invoice_reference else "",
                    "paymentMethod": invoice.payment_method_code,
                    "transactionDetail": transaction_detail,
                    "transactionDate": get_local_formatted_date(invoice.payment_date or invoice.created_on),
                    "templateVars": _receipt_template_vars(invoice),
                },
                topic=current_app.config.get("ACCOUNT_MAILER_TOPIC"),
            )
        )
    except Exception:  # NOQA # pylint: disable=broad-except
        current_app.logger.exception("Receipt notification failed for invoice %s", getattr(invoice, "id", None))


@define
class JobFailureNotification(Serializable):
    """Email notification for job failures."""

    subject: str
    file_name: str
    error_messages: list[dict[str, any]]
    table_name: str
    job_name: str

    def send_notification(self):
        """Send job failure notification email."""
        recipients = current_app.config.get("IT_OPS_EMAIL")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root_dir = os.path.dirname(current_dir)
        templates_dir = os.path.join(project_root_dir, "templates")
        env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)

        template = env.get_template("job_failed_email.html")

        email_params = {
            "jobName": self.job_name,
            "fileName": self.file_name,
            "errorMessages": self.error_messages,
            "tableName": self.table_name,
        }

        if not recipients:
            current_app.logger.info("No recipients found to send email")
            return
        html_body = template.render(email_params)
        send_email_async(recipients=recipients, subject=self.subject, body=html_body)


@define
class ProductRefundEmailContent(Serializable):
    """Product refund email."""

    account_name: str
    account_number: str
    decline_reason: str
    invoice_id: int
    invoice_reference_number: str
    staff_comment: str
    status: str
    reason: str
    refund_amount: Decimal
    url: str

    def render_body(self, status: str, is_for_client: bool) -> str:
        """Render the email body using the provided template."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root_dir = os.path.dirname(current_dir)
        templates_dir = os.path.join(project_root_dir, "templates")
        env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)
        match status:
            case RefundStatus.APPROVED.value | RefundStatus.DECLINED.value:
                if is_for_client:
                    template = env.get_template("product_refund_client_notification.html")
                else:
                    template = env.get_template("product_refund_notification.html")
            case RefundStatus.PENDING_APPROVAL.value:
                template = env.get_template("product_pending_refund_notification.html")
            case _:
                raise ValueError(f"Unsupported refund request status template: {status}")

        return template.render(self.to_dict())
