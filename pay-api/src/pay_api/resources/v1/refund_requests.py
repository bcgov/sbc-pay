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

from pay_api.dtos.refund import RefundRequestGetRequest
from pay_api.exceptions import BusinessException
from pay_api.services import RefundRequestService, RefundService
from pay_api.services.refund_request import RefundRequestsSearch
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import Role, RolePattern
from pay_api.utils.util import iso_string_to_date

bp = Blueprint(
    "REFUND_REQUESTS",
    __name__,
    url_prefix=f"{EndpointEnum.API_V1.value}/refunds",
)


@bp.route("", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
@_jwt.requires_auth
def get_refund_requests():
    """Get refund requests."""
    current_app.logger.info("<get_refund_requests")
    products, filter_by_product = RefundService.check_refund_auth(
        role_pattern=RolePattern.PRODUCT_VIEW_TRANSACTION.value, all_products_role=Role.VIEW_ALL_TRANSACTIONS.value
    )

    request_data = RefundRequestGetRequest.from_dict(request.args.to_dict())
    response, status = (
        RefundRequestService.search(
            RefundRequestsSearch(
                invoice_id=request_data.invoice_id,
                payment_method=request_data.payment_method,
                refund_reason=request_data.refund_reason,
                refund_amount=request_data.refund_amount,
                refund_method=request_data.refund_method,
                requested_by=request_data.requested_by,
                requested_start_date=iso_string_to_date(request_data.requested_start_date),
                requested_end_date=iso_string_to_date(request_data.requested_end_date),
                status=request_data.refund_status,
                transaction_amount=request_data.transaction_amount,
                filter_by_product=filter_by_product,
                allowed_products=products,
                page=request_data.page,
                limit=request_data.limit,
            )
        ),
        HTTPStatus.OK,
    )

    current_app.logger.debug(">get_refund_requests")
    return jsonify(response), status


@bp.route("/<int:refund_id>", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
@cross_origin(origins="*")
@_jwt.requires_auth
def get_refund_request(refund_id: int):
    """Get refund request."""
    current_app.logger.info("<get_refund_request")
    products, filter_by_product = RefundService.check_refund_auth(
        role_pattern=RolePattern.PRODUCT_VIEW_TRANSACTION.value, all_products_role=Role.PRODUCT_REFUND_VIEWER.value
    )

    try:
        if refund := RefundRequestService.find_by_id(refund_id, filter_by_product, products):
            response, status = (
                refund,
                HTTPStatus.OK,
            )
        else:
            response, status = {}, HTTPStatus.NOT_FOUND
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug(">get_refund_request")
    return jsonify(response), status
