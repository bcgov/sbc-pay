# Copyright © 2019 Province of British Columbia
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
"""Service to invoke Rest services which uses OAuth 2.0 implementation."""
import json

import requests
from flask import current_app

from pay_api.utils.enums import AuthHeaderType, ContentType


class OAuthService:
    """Service to invoke Rest services which uses OAuth 2.0 implementation."""

    @staticmethod
    def post(endpoint, token, auth_header_type: AuthHeaderType, content_type: ContentType, data):
        """POST service."""
        current_app.logger.debug('<post')

        headers = {
            'Authorization': auth_header_type.value.format(token),
            'Content-Type': content_type.value
        }
        if content_type == ContentType.JSON:
            data = json.dumps(data)

        current_app.logger.debug('Endpoint : {}'.format(endpoint))
        current_app.logger.debug('headers : {}'.format(headers))
        current_app.logger.debug('data : {}'.format(data))

        response = requests.post(endpoint, data=data, headers=headers)
        current_app.logger.info('response : {}'.format(response.text))
        response.raise_for_status()
        current_app.logger.debug('>post')
        return response
