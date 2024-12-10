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

"""This manages the retrieval of report-api documents."""
from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.services import ReportService
from pay_api.services.report_service import ReportRequest
from pay_api.utils.enums import ContentType, DocumentTemplate, DocumentType
from pay_api.utils.errors import Error


class DocumentsService:
    """Service to manage document retrieval."""

    @classmethod
    def get_document(cls, document_type: str):
        """Get document file."""
        current_app.logger.debug("<get_document")

        if not document_type or document_type not in [doc_type.value for doc_type in DocumentType]:
            raise BusinessException(Error.DOCUMENT_TYPE_INVALID)

        report_name, template_name = cls._get_document_report_params(document_type)
        report_response = ReportService.get_report_response(
            ReportRequest(
                report_name=report_name,
                template_name=template_name,
                content_type=ContentType.PDF.value,
                populate_page_number=True,
            )
        )
        current_app.logger.debug(">get_document")
        return report_response, report_name

    @classmethod
    def _get_document_report_params(cls, document_type: str):
        """Get document report parameters."""
        if document_type == DocumentType.EFT_INSTRUCTIONS.value:
            return "bcrs_eft_instructions.pdf", DocumentTemplate.EFT_INSTRUCTIONS.value
        return None, None
