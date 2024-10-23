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
"""Resource for Transaction endpoints."""
from http import HTTPStatus

from flask import Blueprint, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import TransactionService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.errors import Error
from pay_api.utils.util import is_valid_redirect_url

bp = Blueprint("TRANSACTIONS", __name__, url_prefix=f"{EndpointEnum.API_V1.value}")


@bp.route("/payment-requests/<int:invoice_id>/transactions", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "POST"])
@_jwt.requires_auth
def get_transactions(invoice_id):
    """Get all transaction records for a invoice."""
    current_app.logger.info("<get_transactions")
    response, status = TransactionService.find_by_invoice_id(invoice_id), HTTPStatus.OK
    current_app.logger.debug(">get_transactions")
    return jsonify(response), status


@bp.route("/payment-requests/<int:invoice_id>/transactions", methods=["POST"])
@bp.route("/payments/<int:payment_id>/transactions", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
def post_transaction(invoice_id: int = None, payment_id: int = None):
    """Create the Transaction records."""
    current_app.logger.info("<post_transaction")
    request_json = request.get_json()
    response, status = None, None

    # Validate the input request
    valid_format, errors = schema_utils.validate(request_json, "transaction_request")

    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

    try:
        if invoice_id:
            response, status = (
                TransactionService.create_transaction_for_invoice(invoice_id, request_json).asdict(),
                HTTPStatus.CREATED,
            )
        elif payment_id:
            response, status = (
                TransactionService.create_transaction_for_payment(payment_id, request_json).asdict(),
                HTTPStatus.CREATED,
            )

    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">post_transaction")
    return jsonify(response), status


@bp.route(
    "/payment-requests/<int:invoice_id>/transactions/<uuid:transaction_id>",
    methods=["GET", "OPTIONS"],
)
@bp.route(
    "/payments/<int:payment_id>/transactions/<uuid:transaction_id>",
    methods=["GET", "OPTIONS"],
)
@cross_origin(origins="*", methods=["GET", "PATCH"])
@_jwt.requires_auth
def get_transaction(invoice_id: int = None, payment_id: int = None, transaction_id=None):
    """Get the Transaction record."""
    current_app.logger.info(
        "<Transaction.get for invoice : %s, payment : %s, transaction %s",
        invoice_id,
        payment_id,
        transaction_id,
    )
    try:
        response, status = (
            TransactionService.find_by_id(transaction_id).asdict(),
            HTTPStatus.OK,
        )

    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">get_transaction")
    return jsonify(response), status


@bp.route(
    "/payment-requests/<int:invoice_id>/transactions/<uuid:transaction_id>",
    methods=["PATCH"],
)
@bp.route("/payments/<int:payment_id>/transactions/<uuid:transaction_id>", methods=["PATCH"])
@cross_origin(origins="*")
def patch_transaction(invoice_id: int = None, payment_id: int = None, transaction_id=None):
    """Update the transaction record by querying payment system."""
    current_app.logger.info(
        "<patch_transaction for invoice : %s, payment : %s, transaction %s",
        invoice_id,
        payment_id,
        transaction_id,
    )
    pay_response_url: str = request.get_json().get("payResponseUrl", None)

    try:
        response, status = (
            TransactionService.update_transaction(transaction_id, pay_response_url).asdict(),
            HTTPStatus.OK,
        )
    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">patch_transaction")
    return jsonify(response), status


@bp.route("/valid-redirect-url", methods=["POST"])
@cross_origin(origins="*")
def post_is_valid_redirect_url():
    """Check if the redirect URL is valid."""
    current_app.logger.info("<is_valid_redirect_url")
    is_valid = is_valid_redirect_url(request.get_json().get("redirectUrl", None))
    current_app.logger.debug(">is_valid_redirect_url")
    return jsonify({"isValid": is_valid}), HTTPStatus.OK
