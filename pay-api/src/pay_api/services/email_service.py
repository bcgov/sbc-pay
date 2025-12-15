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

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from attrs import define
from flask import copy_current_request_context, current_app
from jinja2 import Environment, FileSystemLoader

from pay_api.services.auth import get_service_account_token
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import AuthHeaderType, ContentType, RefundStatus
from pay_api.utils.serializable import Serializable

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
    # Note if we send HTML in the body, we aren't sending through GCNotify,
    # ideally we'd like to send through GCNotify.

    @copy_current_request_context
    def _send_email_task(recipients_list: list[str], email_subject: str, email_body: str):
        """Send the email notification in background thread."""
        return send_email(recipients_list, email_subject, email_body)

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
    env = Environment(
        loader=FileSystemLoader(templates_dir), autoescape=True
    )
    template = env.get_template("eft_reverse_payment.html")

    statement_url = (
        f"{current_app.config.get('AUTH_WEB_URL')}/account/"
        f"{params['accountId']}/settings/statements"
    )
    params["statementUrl"] = statement_url

    return template.render(params)


def _render_credit_add_notification_template(params: dict) -> str:
    """Render credit add notification template."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(current_dir)
    templates_dir = os.path.join(project_root_dir, "templates")
    env = Environment(
        loader=FileSystemLoader(templates_dir), autoescape=True
    )
    template = env.get_template("credit_add_notification.html")
    return template.render(params)


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
