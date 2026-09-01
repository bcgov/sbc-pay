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

from flask import Blueprint, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException, ServiceUnavailableException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import TransactionService
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


@bp.route("/<string:token>/transactions", methods=["POST"])
@cross_origin(origins="*", methods=["POST"])
def post_payment_link_transaction(token: str):
    """Start a payment transaction for the invoice behind the token, without signing in.

    Same contract as POST /payment-requests/{invoice_id}/transactions — caller redirects
    to `paySystemUrl`, PayBC returns to the existing PATCH route — except the token has to
    be presented, so a caller can only pay the invoice they were sent a link for.
    """
    current_app.logger.debug("<post_payment_link_transaction")
    request_json = request.get_json()

    valid_format, errors = schema_utils.validate(request_json, "transaction_request")
    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

    try:
        # allow_linked: a payer who already redeemed the link can still pay through it.
        link = PaymentLinkService.resolve_token(token, allow_linked=True)
        response = TransactionService.create_transaction_for_invoice(link.invoice_id, request_json).asdict()
    except ServiceUnavailableException as exception:
        current_app.logger.exception("payment link transaction: downstream 503")
        return exception.response()
    except BusinessException:
        return error_to_response(Error.INVALID_REQUEST)
    current_app.logger.debug(">post_payment_link_transaction")
    return jsonify(response), HTTPStatus.CREATED


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
