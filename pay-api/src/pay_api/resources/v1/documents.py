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
"""Resource for documents endpoints."""

from http import HTTPStatus

from flask import Blueprint, Response, current_app, request
from flask_cors import cross_origin

from pay_api.dtos.documents import DocumentsGetRequest
from pay_api.exceptions import BusinessException
from pay_api.services.documents_service import DocumentsService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import ContentType

bp = Blueprint("DOCUMENTS", __name__, url_prefix=f"{EndpointEnum.API_V1.value}/documents")


@bp.route("", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
@_jwt.requires_auth
def get_documents():
    """Get Pay documents."""
    current_app.logger.info("<get_documents")
    request_data = DocumentsGetRequest.from_dict(request.args.to_dict())

    try:
        report, document_name = DocumentsService.get_document(request_data.document_type)
        response = Response(report, HTTPStatus.OK.value)
        response.headers.set("Content-Disposition", "attachment", filename=document_name)
        response.headers.set("Content-Type", ContentType.PDF.value)
        response.headers.set("Access-Control-Expose-Headers", "Content-Disposition")
        current_app.logger.debug(">get_documents")
        return response
    except BusinessException as exception:
        return exception.response()
