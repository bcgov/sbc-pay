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
"""Resource for Payment account."""
from datetime import datetime, timezone
from http import HTTPStatus

from flask import Blueprint, Response, abort, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException, ServiceUnavailableException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import Payment
from pay_api.services.auth import check_auth
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import EDIT_ROLE, VIEW_ROLE
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import CfsAccountStatus, ContentType, Role
from pay_api.utils.errors import Error

bp = Blueprint("ACCOUNTS", __name__, url_prefix=f"{EndpointEnum.API_V1.value}/accounts")


@bp.route("", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value])
def post_account():
    """Create the payment account records."""
    current_app.logger.info("<post_account")
    request_json = request.get_json()
    current_app.logger.debug(request_json)

    # Check if sandbox request is authorized.
    is_sandbox = request.args.get("sandbox", "false").lower() == "true"
    if is_sandbox and not _jwt.validate_roles([Role.CREATE_SANDBOX_ACCOUNT.value]):
        abort(HTTPStatus.FORBIDDEN)

    # Validate the input request
    valid_format, errors = schema_utils.validate(request_json, "account_info")

    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))
    try:
        response = PaymentAccountService.create(request_json, is_sandbox)
        status = (
            HTTPStatus.ACCEPTED
            if response.cfs_account_id and response.cfs_account_status == CfsAccountStatus.PENDING.value
            else HTTPStatus.CREATED
        )
    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">post_account")
    return jsonify(response.asdict()), status


@bp.route("/search/eft", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def get_eft_accounts():
    """Get all eft-enabled account records."""
    current_app.logger.info("<get_eft_accounts")
    search_text = request.args.get("searchText", None)
    response, status = (
        PaymentAccountService.search_eft_accounts(search_text),
        HTTPStatus.OK,
    )
    current_app.logger.debug(">get_eft_accounts")
    return jsonify(response), status


@bp.route("/<string:account_number>", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "PUT", "DELETE"])
@_jwt.requires_auth
def get_account(account_number: str):
    """Get payment account details."""
    current_app.logger.info("<get_account")
    # Check if user is authorized to perform this action
    check_auth(
        business_identifier=None,
        account_id=account_number,
        one_of_roles=[EDIT_ROLE, VIEW_ROLE],
    )
    response, status = (
        PaymentAccountService.find_by_auth_account_id(account_number).asdict(),
        HTTPStatus.OK,
    )
    current_app.logger.debug(">get_account")
    return jsonify(response), status


@bp.route("/<string:account_number>/eft", methods=["PATCH"])
@cross_origin(origins="*")
@_jwt.has_one_of_roles([Role.SYSTEM.value])
def patch_account(account_number: str):
    """Enable eft for an account."""
    current_app.logger.info("<patch_account_enable_eft")

    try:
        response, status = (
            PaymentAccountService.enable_eft(account_number),
            HTTPStatus.OK,
        )
    except ServiceUnavailableException as exception:
        return exception.response()

    current_app.logger.debug(">patch_account_enable_eft")
    return jsonify(response.asdict()), status


@bp.route("/<string:account_number>", methods=["PUT"])
@cross_origin(origins="*")
@_jwt.has_one_of_roles([Role.SYSTEM.value])
def put_account(account_number: str):
    """Update the payment account records."""
    current_app.logger.info("<put_account")
    request_json = request.get_json()
    current_app.logger.debug(request_json)
    # Validate the input request
    valid_format, errors = schema_utils.validate(request_json, "account_info")

    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))
    try:
        response = PaymentAccountService.update(account_number, request_json)
    except ServiceUnavailableException as exception:
        return exception.response()
    except BusinessException as exception:
        return exception.response()

    status = (
        HTTPStatus.ACCEPTED
        if response.cfs_account_id and response.cfs_account_status == CfsAccountStatus.PENDING.value
        else HTTPStatus.OK
    )

    current_app.logger.debug(">put_account")
    return jsonify(response.asdict()), status


@bp.route("/<string:account_number>", methods=["DELETE"])
@cross_origin(origins="*")
@_jwt.has_one_of_roles([Role.SYSTEM.value])
def delete_account(account_number: str):
    """Delete payment account details."""
    current_app.logger.info("<delete_account")
    # Check if user is authorized to perform this action
    check_auth(
        business_identifier=None,
        account_id=account_number,
        one_of_roles=[EDIT_ROLE, VIEW_ROLE],
    )
    try:
        PaymentAccountService.delete_account(account_number)
    except BusinessException as exception:
        return exception.response()
    except ServiceUnavailableException as exception:
        return exception.response()
    current_app.logger.debug(">delete_account")
    return jsonify({}), HTTPStatus.NO_CONTENT


@bp.route("/<string:account_number>/fees", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "POST", "DELETE"])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.MANAGE_ACCOUNTS.value])
def get_account_fees(account_number: str):
    """Get Fee details for the account."""
    current_app.logger.info("<get_account_fees")
    response, status = (
        PaymentAccountService.get_account_fees(account_number),
        HTTPStatus.OK,
    )
    current_app.logger.debug(">get_account_fees")
    return jsonify(response), status


@bp.route("/<string:account_number>/fees", methods=["POST"])
@cross_origin(origins="*")
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.MANAGE_ACCOUNTS.value])
def post_account_fees(account_number: str):
    """Create or update the account fee settings."""
    current_app.logger.info("<post_account_fees")
    request_json = request.get_json()
    # Validate the input request
    valid_format, errors = schema_utils.validate(request_json, "account_fees")

    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))
    try:
        response, status = (
            PaymentAccountService.save_account_fees(account_number, request_json),
            HTTPStatus.OK,
        )
    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">post_account_fees")
    return jsonify(response), status


@bp.route("/<string:account_number>/fees", methods=["DELETE"])
@cross_origin(origins="*")
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.MANAGE_ACCOUNTS.value])
def delete_account_fees(account_number: str):
    """Remove the account fee settings."""
    current_app.logger.info("<delete_account_fees")
    PaymentAccountService.delete_account_fees(account_number)
    current_app.logger.debug(">delete_account_fees")
    return jsonify({}), HTTPStatus.NO_CONTENT


@bp.route("/<string:account_number>/fees/<string:product>", methods=["PUT", "OPTIONS"])
@cross_origin(origins="*", methods=["PUT"])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.MANAGE_ACCOUNTS.value])
def put_account_fee_product(account_number: str, product: str):
    """Create or update the account fee settings."""
    current_app.logger.info("<put_account_fee_product")
    request_json = request.get_json()
    # Validate the input request
    valid_format, errors = schema_utils.validate(request_json, "account_fee")

    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))
    try:
        response, status = (
            PaymentAccountService.save_account_fee(account_number, product, request_json),
            HTTPStatus.OK,
        )
    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">put_account_fee_product")
    return jsonify(response), status


#########################################################################################################
# Note this route is used by CSO for reconciliation, so be careful if making any changes to the response.
#########################################################################################################


@bp.route("/<string:account_number>/payments/queries", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
@_jwt.requires_auth
def post_search_purchase_history(account_number: str):
    """Search purchase history."""
    current_app.logger.info("<post_search_purchase_history")

    request_json = request.get_json()
    current_app.logger.debug(request_json)
    valid_format, errors = schema_utils.validate(request_json, "purchase_history_request")
    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))
    if account_number == "undefined":
        return error_to_response(Error.INVALID_REQUEST, invalid_params="account_number")

    any_org_transactions = request.args.get("viewAll", None) == "true"
    if any_org_transactions:
        check_auth(business_identifier=None, account_id=account_number,
                   all_of_roles=[Role.EDITOR.value, Role.VIEW_ALL_TRANSACTIONS.value])
    else:
        check_auth(business_identifier=None, account_id=account_number,
                   one_of_roles=[Role.EDITOR.value, Role.VIEW_ACCOUNT_TRANSACTIONS.value])

    account_to_search = None if any_org_transactions else account_number
    page: int = int(request.args.get("page", "1"))
    limit: int = int(request.args.get("limit", "10"))
    response, status = (
        Payment.search_purchase_history(account_to_search, request_json, page, limit),
        HTTPStatus.OK,
    )
    current_app.logger.debug(">post_search_purchase_history")
    return jsonify(response), status


@bp.route("/<string:account_number>/payments/reports", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
@_jwt.requires_auth
def post_account_purchase_report(account_number: str):
    """Create the account purchase report."""
    current_app.logger.info("<post_account_purchase_report")
    response_content_type = request.headers.get("Accept", ContentType.PDF.value)
    request_json = request.get_json()
    current_app.logger.debug(request_json)
    # Validate the input request
    valid_format, errors = schema_utils.validate(request_json, "purchase_history_request")
    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

    report_name = f"bcregistry-transactions-{datetime.now(tz=timezone.utc).strftime('%m-%d-%Y')}"

    if response_content_type == ContentType.PDF.value:
        report_name = f"{report_name}.pdf"
    else:
        report_name = f"{report_name}.csv"

    # Check if user is authorized to perform this action
    check_auth(business_identifier=None, account_id=account_number,
               one_of_roles=[EDIT_ROLE, Role.VIEW_ACCOUNT_TRANSACTIONS.value])
    try:
        report = Payment.create_payment_report(account_number, request_json, response_content_type, report_name)
        response = Response(report, 201)
        response.headers.set("Content-Disposition", "attachment", filename=report_name)
        response.headers.set("Content-Type", response_content_type)
        response.headers.set("Access-Control-Expose-Headers", "Content-Disposition")
        return response
    except BusinessException as exception:
        return exception.response()
