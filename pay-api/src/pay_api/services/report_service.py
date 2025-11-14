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
"""Service to manage report generation."""

from dataclasses import dataclass

from flask import current_app

from pay_api.utils.user_context import user_context

from ..utils.enums import AuthHeaderType, ContentType  # noqa: TID252
from .oauth_service import OAuthService


@dataclass
class ReportRequest:
    """Used for reportAPI request payload."""

    content_type: str
    report_name: str
    template_name: str
    populate_page_number: bool
    template_vars: dict | None = None
    stream: bool = False


class ReportService:
    """Service to manage report generation."""

    @staticmethod
    def get_request_payload(request: ReportRequest) -> dict:
        """Return report request payload dictionary."""
        return {
            "reportName": request.report_name,
            "templateName": request.template_name,
            "templateVars": request.template_vars or {},
            "populatePageNumber": request.populate_page_number,
        }

    @classmethod
    @user_context
    def get_report_response(cls, request: ReportRequest, **kwargs):
        """Return report response from report-api."""
        report_payload = cls.get_request_payload(request)

        return OAuthService.post(
            endpoint=current_app.config.get("REPORT_API_BASE_URL"),
            token=kwargs["user"].bearer_token,
            auth_header_type=AuthHeaderType.BEARER,
            content_type=ContentType.JSON,
            additional_headers={"Accept": request.content_type},
            data=report_payload,
            stream=request.stream,
            gzip_body=True,
        )
