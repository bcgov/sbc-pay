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
"""Resource for Account payments endpoints."""

from http import HTTPStatus

from flask import Blueprint, current_app, g, jsonify, request
from flask_cors import cross_origin

from pay_api.exceptions import error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import Payment as PaymentService
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import EDIT_ROLE, MAKE_PAYMENT, VIEW_ROLE
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import PaymentMethod, Role
from pay_api.utils.errors import Error

bp = Blueprint(
    "PAYMENTS",
    __name__,
    url_prefix=f"{EndpointEnum.API_V1.value}/accounts/<string:account_id>/payments",
)


@bp.route("", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "POST"])
@_jwt.requires_auth
def get_account_payments(account_id: str):
    """Get account payments."""
    current_app.logger.info("<get_account_payments")
    # Check if user is authorized to perform this action
    check_auth(
        business_identifier=None,
        account_id=account_id,
        one_of_roles=[MAKE_PAYMENT, EDIT_ROLE, VIEW_ROLE],
    )
    page: int = int(request.args.get("page", "1"))
    limit: int = int(request.args.get("limit", "10"))
    status: str = request.args.get("status", None)
    response, status = (
        PaymentService.search_account_payments(auth_account_id=account_id, status=status, page=page, limit=limit),
        HTTPStatus.OK,
    )
    current_app.logger.debug(">get_account_payments")
    return jsonify(response), status


@bp.route("", methods=["POST"])
@cross_origin(origins="*")
@_jwt.requires_auth
def post_account_payment(account_id: str):
    """Create account payments."""
    current_app.logger.info("<post_account_payment")
    response, status = None, None
    # Check if user is authorized to perform this action
    check_auth(business_identifier=None, account_id=account_id, contains_role=MAKE_PAYMENT)
    # If it's a staff user, then create credits.
    if {Role.STAFF.value, Role.CREATE_CREDITS.value}.issubset(set(g.jwt_oidc_token_info.get("roles"))):
        credit_request = request.get_json()
        # Valid payment payload.
        valid_format, errors = schema_utils.validate(credit_request, "payment")
        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        if credit_request.get("paymentMethod") in (
            PaymentMethod.EFT.value,
            PaymentMethod.DRAWDOWN.value,
        ):
            response, status = (
                PaymentService.create_payment_receipt(
                    auth_account_id=account_id, credit_request=credit_request
                ).asdict(),
                HTTPStatus.CREATED,
            )
    else:
        is_retry_payment: bool = request.args.get("retryFailedPayment", "false").lower() == "true"
        pay_outstanding_balance = False
        all_invoice_statuses = False
        pay_outstanding_balance = request.args.get("payOutstandingBalance", "false").lower() == "true"
        all_invoice_statuses = request.args.get("allInvoiceStatuses", "false").lower() == "true"

        response, status = (
            PaymentService.create_account_payment(
                auth_account_id=account_id,
                is_retry_payment=is_retry_payment,
                pay_outstanding_balance=pay_outstanding_balance,
                all_invoice_statuses=all_invoice_statuses,
            ).asdict(),
            HTTPStatus.CREATED,
        )

    current_app.logger.debug(">post_account_payment")
    return jsonify(response), status
