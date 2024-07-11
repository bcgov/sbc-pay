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

from flask import current_app
from pay_api.exceptions import ServiceUnavailableException
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import AuthHeaderType, ContentType
from pay_api.utils.user_context import user_context


@user_context
def send_email(recipients: str, subject: str, html_body: str, **kwargs):  # pylint:disable=unused-argument
    """Send the email asynchronously, using the given details."""
    token = kwargs['user'].bearer_token
    current_app.logger.info(f'>send_email to recipients: {recipients}')
    notify_url = current_app.config.get('NOTIFY_API_ENDPOINT') + 'notify/'
    notify_body = {
        'recipients': recipients,
        'content': {
            'subject': subject,
            'body': html_body
        }
    }

    try:
        notify_response = OAuthService.post(notify_url, token=token,
                                            auth_header_type=AuthHeaderType.BEARER,
                                            content_type=ContentType.JSON, data=notify_body)
        current_app.logger.info('<send_email notify_response')
        if notify_response:
            response_json = json.loads(notify_response.text)
            if response_json.get('notifyStatus', 'FAILURE') != 'FAILURE':
                return True
    except ServiceUnavailableException as e:
        current_app.logger.error(e)

    return False
