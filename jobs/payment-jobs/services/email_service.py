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
from decimal import Decimal
from typing import Dict

from attr import define
from flask import current_app
from jinja2 import Environment, FileSystemLoader
from pay_api.services.auth import get_service_account_token
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import AuthHeaderType, ContentType


def send_email(recipients: list[str], subject: str, body: str):
    """Send the email notification."""
    # Note if we send HTML in the body, we aren't sending through GCNotify, ideally we'd like to send through GCNotify.
    token = get_service_account_token()
    current_app.logger.info(f">send_email to recipients: {recipients}")
    notify_url = current_app.config.get("NOTIFY_API_ENDPOINT") + "notify/"
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
                current_app.logger.info(f"Successfully sent email to {recipients}")
        except Exception as e:  # NOQA pylint:disable=broad-except
            current_app.logger.error(f"Error sending email to {recipients}: {e}")


def _get_template(template_file_name: str):
    """Retrieve template."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(current_dir)
    templates_dir = os.path.join(project_root_dir, "templates")
    env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)
    return env.get_template(template_file_name)


def _render_eft_overpayment_template(params: Dict) -> str:
    """Render eft overpayment template."""
    template = _get_template("eft_overpayment.html")
    short_name_detail_url = f"{current_app.config.get('AUTH_WEB_URL')}/pay/shortname-details/{params['shortNameId']}"
    params["shortNameDetailUrl"] = short_name_detail_url

    return template.render(params)
