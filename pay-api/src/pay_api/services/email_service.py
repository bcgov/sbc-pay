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

import base64
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from attrs import define
from flask import copy_current_request_context, current_app, has_request_context
from jinja2 import Environment, FileSystemLoader

from pay_api.models import InvoicePaymentLink as InvoicePaymentLinkModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.services.auth import get_account_members, get_service_account_token
from pay_api.services.oauth_service import OAuthService
from pay_api.services.receipt import Receipt as ReceiptService
from pay_api.utils.enums import AuthHeaderType, ContentType, InvoiceReferenceStatus, RefundStatus
from pay_api.utils.serializable import Serializable
from pay_api.utils.util import get_local_formatted_date

_executor = ThreadPoolExecutor(max_workers=5)


def _pdf_attachment(file_name: str, content: bytes, order: int = 1) -> dict:
    """Shape a PDF into notify-api's attachment contract.

    See `AttachmentRequest` in bcros-common/notify-service: `fileName` and `attachOrder`
    are required, and it accepts either `fileBytes` or `fileUrl` — we inline the bytes.
    """
    return {
        "fileName": file_name,
        "fileBytes": base64.b64encode(content).decode("utf-8"),
        "attachOrder": str(order),
    }


def send_email(recipients: list[str], subject: str, body: str, attachments: list[dict] | None = None):
    """Send the email notification."""
    # Note if we send HTML in the body, we aren't sending through GCNotify,
    # ideally we'd like to send through GCNotify.
    token = get_service_account_token()
    current_app.logger.info(f">send_email to recipients: {recipients}")
    notify_url = current_app.config.get("NOTIFY_API_ENDPOINT") + "notify/"

    success = False

    for recipient in recipients:
        content = {"subject": subject, "body": body}
        if attachments:
            content["attachments"] = attachments
        notify_body = {
            "recipients": recipient,
            "content": content,
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


def send_email_async(recipients: list[str], subject: str, body: str, attachments: list[dict] | None = None):
    """Send the email notification asynchronously using ThreadExecutor.

    Args:
        recipients: List of email recipients
        subject: Email subject
        body: Email body
        attachments: Optional notify-api attachment dicts

    Returns:
        Future object representing the asynchronous email sending task
    """
    app = current_app._get_current_object()

    def _send_email_task(recipients_list, email_subject, email_body, email_attachments):
        """Send the email notification in background thread."""
        if has_request_context():

            @copy_current_request_context
            def _inner():
                return send_email(recipients_list, email_subject, email_body, email_attachments)
        else:

            def _inner():
                with app.app_context():
                    return send_email(recipients_list, email_subject, email_body, email_attachments)

        return _inner()

    return _executor.submit(_send_email_task, recipients, subject, body, attachments)


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


def _render_receipt_notification_template(params: dict) -> str:
    """Render the post-payment receipt notification template."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(current_dir)
    templates_dir = os.path.join(project_root_dir, "templates")
    env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)
    return env.get_template("receipt_notification.html").render(params)


def _receipt_attachment(invoice) -> list[dict]:
    """Return the receipt PDF as a notify-api attachment, or [] if one can't be produced.

    Whether an invoice has a receipt yet is the receipt service's call, not this module's —
    it refuses an unpaid card invoice and renders a "payment pending" receipt for PAD and
    EFT. Either way this stays defensive: an email without the receipt beats no email, and
    the body already tells the reader a pending receipt will follow.
    """
    try:
        pdf = b"".join(
            ReceiptService.create_receipt(
                invoice.id,
                {"filingDateTime": get_local_formatted_date(invoice.created_on)},
                skip_auth_check=True,
                use_service_account=True,
            )
        )
        return [_pdf_attachment(f"bcregistry-receipt-{invoice.id}.pdf", pdf)]
    except Exception:  # NOQA # pylint: disable=broad-except
        current_app.logger.exception("Could not build the receipt attachment for invoice %s", invoice.id)
        return []


def send_receipt_notification(invoice):
    """Email the account's admins and coordinators after a payment settles.

    Called from both pay-api and pay-queue — card payments settle on the PayBC return,
    OB and PAD later in reconciliation.

    An express-checkout invoice whose link nobody claimed has no account and no admins, so
    it goes to the address the partner supplied at invoice creation, and the template drops
    the account rows. Without that address there is nobody to tell.

    Mail failures are logged and never affect the payment.
    """
    try:
        payment_account = PaymentAccountModel.find_by_id(invoice.payment_account_id)
        if not payment_account:
            current_app.logger.info("No payment account found for invoice %s", invoice.id)
            return
        auth_account_id = payment_account.auth_account_id if payment_account else None
        unredeemed_link = InvoicePaymentLinkModel.find_unredeemed_for_invoice(invoice.id)
        is_guest = unredeemed_link is not None

        if is_guest:
            recipients = [unredeemed_link.email] if unredeemed_link.email else []
            account_name_with_branch = ""
        elif not auth_account_id:
            return
        else:
            members = (
                get_account_members(auth_account_id, use_service_account=True, roles="ADMIN,COORDINATOR").get("members")
                or []
            )
            recipients = [
                email
                for member in members
                if (user := member.get("user"))
                and (contacts := user.get("contacts"))
                and (email := contacts[0].get("email"))
            ]
            account_name = payment_account.name or ""
            branch_name = payment_account.branch_name
            account_name_with_branch = (
                f"{account_name}-{branch_name}" if branch_name and branch_name not in account_name else account_name
            )

        if not recipients:
            current_app.logger.info("No one to send the receipt for invoice %s to; skipping.", invoice.id)
            return

        invoice_reference = InvoiceReferenceModel.find_by_invoice_id_and_status(
            invoice.id, InvoiceReferenceStatus.COMPLETED.value
        )
        # Must read the same as the fee summary, so use its line-item descriptions.
        transaction_detail = ", ".join(
            line.description for line in (invoice.payment_line_items or []) if line.description
        )
        html_body = _render_receipt_notification_template(
            {
                "amount": f"{float(invoice.total):.2f}",
                "account_number": "" if is_guest else auth_account_id,
                "account_name_with_branch": account_name_with_branch,
                "invoice_number": invoice_reference.invoice_number if invoice_reference else "",
                "payment_method": invoice.payment_method_code,
                "transaction_detail": transaction_detail,
                "transaction_date": get_local_formatted_date(invoice.payment_date or invoice.created_on),
                "transactions_url": (
                    ""
                    if is_guest
                    else f"{current_app.config.get('AUTH_WEB_URL')}/account/{auth_account_id}/settings/transactions"
                ),
            }
        )
        send_email_async(
            recipients,
            f"Payment received for invoice {invoice.id}",
            html_body,
            _receipt_attachment(invoice),
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
