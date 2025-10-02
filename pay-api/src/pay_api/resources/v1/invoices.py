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
"""Resource for Invoice endpoints."""

from http import HTTPStatus

from flask import Blueprint, jsonify
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException
from pay_api.services import InvoiceService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum

bp = Blueprint(
    "INVOICES",
    __name__,
    url_prefix=f"{EndpointEnum.API_V1.value}/payment-requests/<int:invoice_id>/invoices",
)


@bp.route("", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
@_jwt.requires_auth
def get_invoice_by_id(invoice_id):
    """Subject to remove once the change has been notified to teams."""
    try:
        response = {"items": []}

        response["items"].append(InvoiceService.asdict(InvoiceService.find_by_id(invoice_id)))
    except BusinessException as exception:
        return exception.response()
    return jsonify(response), HTTPStatus.OK
