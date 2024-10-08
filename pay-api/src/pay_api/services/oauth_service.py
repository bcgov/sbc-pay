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
"""Service to invoke Rest services."""
import json
import re
from collections.abc import Iterable
from typing import Dict

import requests
from flask import current_app
from requests.adapters import HTTPAdapter  # pylint:disable=ungrouped-imports
from requests.exceptions import ConnectionError as ReqConnectionError  # pylint:disable=ungrouped-imports
from requests.exceptions import ConnectTimeout, HTTPError
from urllib3.util.retry import Retry

from pay_api.exceptions import ServiceUnavailableException
from pay_api.utils.enums import AuthHeaderType, ContentType
from pay_api.utils.json_util import DecimalEncoder

RETRY_ADAPTER = HTTPAdapter(max_retries=Retry(total=5, backoff_factor=1, status_forcelist=[404]))


class OAuthService:
    """Service to invoke Rest services which uses OAuth 2.0 implementation."""

    @staticmethod
    def post(  # pylint: disable=too-many-arguments
        endpoint,
        token,
        auth_header_type: AuthHeaderType,
        content_type: ContentType,
        data,
        raise_for_error: bool = True,
        additional_headers: Dict = None,
        is_put: bool = False,
        auth_header_name: str = "Authorization",
    ):
        """POST service."""
        current_app.logger.debug("<post")

        headers = {
            auth_header_name: auth_header_type.value.format(token),
            "Content-Type": content_type.value,
        }

        if additional_headers:
            headers.update(additional_headers)

        if content_type == ContentType.JSON:
            data = json.dumps(data, cls=DecimalEncoder)

        safe_headers = headers.copy()
        safe_headers.pop("Authorization", None)
        current_app.logger.debug(f"Endpoint : {endpoint}")
        current_app.logger.debug(f"headers : {safe_headers}")
        current_app.logger.debug(f"data : {data}")
        response = None
        try:
            if is_put:
                response = requests.put(
                    endpoint,
                    data=data,
                    headers=headers,
                    timeout=current_app.config.get("CONNECT_TIMEOUT"),
                )
            else:
                response = requests.post(
                    endpoint,
                    data=data,
                    headers=headers,
                    timeout=current_app.config.get("CONNECT_TIMEOUT"),
                )
            if raise_for_error:
                response.raise_for_status()
        except (ReqConnectionError, ConnectTimeout) as exc:
            current_app.logger.error("---Error on POST---")
            current_app.logger.error(exc)
            raise ServiceUnavailableException(exc) from exc
        except HTTPError as exc:
            current_app.logger.error(
                f"HTTPError on POST with status code {exc.response.status_code if exc.response is not None else ''}"
            )
            if exc.response and exc.response.status_code >= 500:
                raise ServiceUnavailableException(exc) from exc
            raise exc
        finally:
            OAuthService.__log_response(response)

        current_app.logger.debug(">post")
        return response

    @staticmethod
    def __log_response(response):
        if response is not None:
            current_app.logger.info(f"Response Headers {response.headers}")
            if (
                response.headers
                and isinstance(response.headers, Iterable)
                and "Content-Type" in response.headers
                and response.headers["Content-Type"] == ContentType.JSON.value
            ):
                # Remove authentication from response
                response_text = response.text if response is not None else ""
                response_text = re.sub(r'"access_token"\s*:\s*"[^"]*",?\s*', "", response_text)
                response_text = re.sub(r",\s*}", "}", response_text)
                current_app.logger.info(f"response : {response_text}")

    @staticmethod
    def get(  # pylint:disable=too-many-arguments
        endpoint,
        token,
        auth_header_type: AuthHeaderType,
        content_type: ContentType,
        retry_on_failure: bool = False,
        return_none_if_404: bool = False,
        additional_headers: Dict = None,
        auth_header_name: str = "Authorization",
    ):
        """GET service."""
        current_app.logger.debug("<GET")

        headers = {
            auth_header_name: auth_header_type.value.format(token),
            "Content-Type": content_type.value,
        }

        if additional_headers is not None:
            headers.update(additional_headers)

        safe_headers = headers.copy()
        safe_headers.pop("Authorization", None)
        current_app.logger.debug(f"Endpoint : {endpoint}")
        current_app.logger.debug(f"headers : {safe_headers}")
        session = requests.Session()
        if retry_on_failure:
            session.mount(endpoint, RETRY_ADAPTER)
        response = None
        try:
            response = session.get(
                endpoint,
                headers=headers,
                timeout=current_app.config.get("CONNECT_TIMEOUT"),
            )
            response.raise_for_status()
        except (ReqConnectionError, ConnectTimeout) as exc:
            current_app.logger.error("---Error on GET---")
            current_app.logger.error(exc)
            raise ServiceUnavailableException(exc) from exc
        except HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                current_app.logger.error(
                    "HTTPError on GET with status code "
                    f"{exc.response.status_code if exc.response is not None else ''}"
                )
            if exc.response is not None:
                if exc.response.status_code >= 500:
                    raise ServiceUnavailableException(exc) from exc
                if return_none_if_404 and exc.response.status_code == 404:
                    return None
            raise exc
        finally:
            OAuthService.__log_response(response)

        current_app.logger.debug(">GET")
        return response
