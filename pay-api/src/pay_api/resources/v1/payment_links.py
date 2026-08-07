# Copyright © 2026 Province of British Columbia
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
"""Resource for express-checkout payment link endpoints.

A payment link is an opaque token that references a single invoice created via the
express-checkout (partner service-account) flow. The token itself grants read of the
invoice summary; redeeming it binds the invoice to the caller's auth account so they
can pay.
"""

from http import HTTPStatus

from flask import Blueprint, current_app, jsonify
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException, ServiceUnavailableException, error_to_response
from pay_api.services.payment_link import PaymentLinkService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.errors import Error

bp = Blueprint("PAYMENT_LINKS", __name__, url_prefix=f"{EndpointEnum.API_V1.value}/payment-links")


@bp.route("/<string:token>", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
@_jwt.requires_auth
def get_payment_link(token: str):
    """Return the invoice DTO the payment link refers to."""
    current_app.logger.debug("<get_payment_link")
    try:
        response = PaymentLinkService.find_invoice_by_token(token)
    except BusinessException:
        return error_to_response(Error.INVALID_REQUEST)
    current_app.logger.debug(">get_payment_link")
    return jsonify(response), HTTPStatus.OK


@bp.route("/<string:token>/redemption", methods=["POST"])
@cross_origin(origins="*")
@_jwt.requires_auth
def post_payment_link_redemption(token: str):
    """Bind the invoice behind the payment link to the caller's auth account.

    Idempotent for the account that first claimed the link. Response is a uniform
    INVALID_REQUEST for any token that doesn't resolve (unknown / expired / already
    bound to another account) to avoid enumeration signal.
    """
    current_app.logger.debug("<post_payment_link_redemption")
    try:
        response = PaymentLinkService.redeem(token)
    except ServiceUnavailableException as exception:
        current_app.logger.exception("payment link redemption: downstream 503")
        return exception.response()
    except BusinessException:
        return error_to_response(Error.INVALID_REQUEST)
    current_app.logger.debug(">post_payment_link_redemption")
    return jsonify(response), HTTPStatus.OK
