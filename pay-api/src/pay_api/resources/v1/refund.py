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
"""Resource for Refunds endpoints."""

from http import HTTPStatus

from flask import Blueprint, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.dtos.refund import RefundPatchRequest
from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import RefundService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import Role, RolePattern
from pay_api.utils.errors import Error

bp = Blueprint(
    "REFUNDS",
    __name__,
    url_prefix=f"{EndpointEnum.API_V1.value}/payment-requests/<int:invoice_id>",
)


@bp.route("/refunds", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
@_jwt.requires_auth
def post_refund(invoice_id):
    """Create the Refund for the Invoice."""
    current_app.logger.info(f"<post_refund : {invoice_id}")
    products, _ = RefundService.check_refund_auth(
        role_pattern=RolePattern.PRODUCT_REFUND_REQUESTER.value, all_products_role=Role.PRODUCT_REFUND_REQUESTER.value
    )

    request_json = request.get_json(silent=True)
    try:
        valid_format, errors = schema_utils.validate(request_json, "refund") if request_json else (True, None)
        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        response = RefundService.create_refund(invoice_id, request_json, products)

    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(f">post_refund : {invoice_id}")
    return jsonify(response), HTTPStatus.ACCEPTED


@bp.route("/refunds/<int:refund_id>", methods=["PATCH"])
@cross_origin(origins="*")
@_jwt.requires_auth
def patch_refund(invoice_id: int, refund_id: int):
    """Patch refund."""
    current_app.logger.info("<patch_refund")
    products, _ = RefundService.check_refund_auth(
        role_pattern=RolePattern.PRODUCT_REFUND_APPROVER.value, all_products_role=Role.PRODUCT_REFUND_APPROVER.value
    )
    request_json = request.get_json()
    refund_request = RefundPatchRequest.from_dict(request_json)
    try:
        if refund_model := RefundService.find_by_invoice_and_refund_id(invoice_id, refund_id):
            response, status = (
                RefundService.approve_or_decline_refund(refund_model, refund_request, products),
                HTTPStatus.OK,
            )
        else:
            response, status = {}, HTTPStatus.NOT_FOUND
    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">patch_refund")
    return jsonify(response), status
