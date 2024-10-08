# Copyright © 2023 Province of British Columbia
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
"""Resource for EFT Short name."""
from http import HTTPStatus

from flask import Blueprint, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.dtos.eft_shortname import (
    EFTShortNameGetRequest,
    EFTShortNameRefundGetRequest,
    EFTShortNameRefundPatchRequest,
    EFTShortNameSummaryGetRequest,
)
from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services.eft_refund import EFTRefund as EFTRefundService
from pay_api.services.eft_short_name_historical import EFTShortnameHistorical as EFTShortnameHistoryService
from pay_api.services.eft_short_name_historical import EFTShortnameHistorySearch
from pay_api.services.eft_short_name_summaries import EFTShortnameSummaries as EFTShortnameSummariesService
from pay_api.services.eft_short_names import EFTShortnames as EFTShortnameService
from pay_api.services.eft_short_names import EFTShortnamesSearch
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import Role
from pay_api.utils.errors import Error
from pay_api.utils.util import string_to_date, string_to_decimal, string_to_int

bp = Blueprint(
    "EFT_SHORT_NAMES",
    __name__,
    url_prefix=f"{EndpointEnum.API_V1.value}/eft-shortnames",
)


@bp.route("", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def get_eft_shortnames():
    """Get all eft short name records."""
    current_app.logger.info("<get_eft_shortnames")
    request_data = EFTShortNameGetRequest.from_dict(request.args.to_dict())
    response, status = (
        EFTShortnameService.search(
            EFTShortnamesSearch(
                id=request_data.short_name_id,
                account_id=request_data.account_id,
                account_id_list=request_data.account_id_list,
                account_name=request_data.account_name,
                account_branch=request_data.account_branch,
                amount_owing=string_to_decimal(request_data.amount_owing),
                short_name=request_data.short_name,
                short_name_type=request_data.short_name_type,
                statement_id=string_to_int(request_data.statement_id),
                state=request_data.state,
                page=request_data.page,
                limit=request_data.limit,
            )
        ),
        HTTPStatus.OK,
    )
    current_app.logger.debug(">get_eft_shortnames")
    return jsonify(response), status


@bp.route("/summaries", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def get_eft_shortname_summaries():
    """Get all eft short name summaries."""
    current_app.logger.info("<get_eft_shortname_summaries")
    request_data = EFTShortNameSummaryGetRequest.from_dict(request.args.to_dict())
    response, status = (
        EFTShortnameSummariesService.search(
            EFTShortnamesSearch(
                id=string_to_int(request_data.short_name_id),
                deposit_start_date=string_to_date(request_data.payment_received_start_date),
                deposit_end_date=string_to_date(request_data.payment_received_end_date),
                credit_remaining=string_to_decimal(request_data.credits_remaining),
                linked_accounts_count=string_to_int(request_data.linked_accounts_count),
                short_name=request_data.short_name,
                short_name_type=request_data.short_name_type,
                page=request_data.page,
                limit=request_data.limit,
            )
        ),
        HTTPStatus.OK,
    )

    current_app.logger.debug(">get_eft_shortname_summaries")
    return jsonify(response), status


@bp.route("/<int:short_name_id>", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "PATCH"])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def get_eft_shortname(short_name_id: int):
    """Get EFT short name details."""
    current_app.logger.info("<get_eft_shortname")

    if not (eft_short_name := EFTShortnameService.find_by_short_name_id(short_name_id)):
        response, status = {}, HTTPStatus.NOT_FOUND
    else:
        response, status = eft_short_name, HTTPStatus.OK
    current_app.logger.debug(">get_eft_shortname")
    return jsonify(response), status


@bp.route("/<int:short_name_id>", methods=["PATCH"])
@cross_origin(origins="*")
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def patch_eft_shortname(short_name_id: int):
    """Patch EFT short name."""
    current_app.logger.info("<patch_eft_shortname")
    request_json = request.get_json()
    valid_format, errors = schema_utils.validate(request_json, "eft_short_name")
    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))
    try:
        response, status = (
            EFTShortnameService.patch_shortname(short_name_id, request_json),
            HTTPStatus.OK,
        )
    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">patch_eft_shortname")
    return jsonify(response), status


@bp.route("/<int:short_name_id>/history", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def get_eft_shortname_history(short_name_id: int):
    """Get EFT short name history."""
    current_app.logger.info("<get_eft_shortname_history")

    page: int = int(request.args.get("page", "1"))
    limit: int = int(request.args.get("limit", "10"))

    response, status = (
        EFTShortnameHistoryService.search(short_name_id, EFTShortnameHistorySearch(page=page, limit=limit)),
        HTTPStatus.OK,
    )
    current_app.logger.debug(">get_eft_shortname_history")
    return jsonify(response), status


@bp.route("/<int:short_name_id>/links", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "POST", "PATCH"])
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def get_eft_shortname_links(short_name_id: int):
    """Get EFT short name account links."""
    current_app.logger.info("<get_eft_shortname_links")

    try:
        if not EFTShortnameService.find_by_short_name_id(short_name_id):
            response, status = {}, HTTPStatus.NOT_FOUND
        else:
            response, status = (
                EFTShortnameService.get_shortname_links(short_name_id),
                HTTPStatus.OK,
            )
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug(">get_eft_shortname_links")
    return jsonify(response), status


@bp.route("/<int:short_name_id>/links", methods=["POST"])
@cross_origin(origins="*")
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def post_eft_shortname_link(short_name_id: int):
    """Create EFT short name to account link."""
    current_app.logger.info("<post_eft_shortname_link")
    request_json = request.get_json()

    try:
        if not EFTShortnameService.find_by_short_name_id(short_name_id):
            response, status = {}, HTTPStatus.NOT_FOUND
        else:
            account_id = request_json.get("accountId", None)
            response, status = (
                EFTShortnameService.create_shortname_link(short_name_id, account_id),
                HTTPStatus.OK,
            )
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug(">post_eft_shortname_link")
    return jsonify(response), status


@bp.route("/<int:short_name_id>/links/<int:short_name_link_id>", methods=["PATCH"])
@cross_origin(origins="*")
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def patch_eft_shortname_link(short_name_id: int, short_name_link_id: int):
    """Patch EFT short name link."""
    current_app.logger.info("<patch_eft_shortname_link")
    request_json = request.get_json()

    try:
        link = EFTShortnameService.find_link_by_id(short_name_link_id)
        if not link or link["short_name_id"] != short_name_id:
            response, status = {}, HTTPStatus.NOT_FOUND
        else:
            response, status = (
                EFTShortnameService.patch_shortname_link(short_name_link_id, request_json),
                HTTPStatus.OK,
            )
    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">patch_eft_shortname_link")
    return jsonify(response), status


@bp.route("/<int:short_name_id>/payment", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def post_eft_statement_payment(short_name_id: int):
    """Perform EFT short name payment action on statement."""
    current_app.logger.info("<post_eft_statement_payment")
    request_json = request.get_json()

    try:
        if not EFTShortnameService.find_by_short_name_id(short_name_id):
            response, status = {}, HTTPStatus.NOT_FOUND
        else:
            valid_format, errors = schema_utils.validate(request_json, "eft_payment")
            if not valid_format:
                return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

            response, status = (
                EFTShortnameService.process_payment_action(short_name_id, request_json),
                HTTPStatus.NO_CONTENT,
            )
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug(">post_eft_statement_payment")
    return jsonify(response), status


@bp.route("/shortname-refund", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "POST", "PATCH"])
@_jwt.has_one_of_roles([Role.EFT_REFUND.value, Role.EFT_REFUND_APPROVER.value])
def get_shortname_refunds():
    """Get all short name refunds."""
    request_data = EFTShortNameRefundGetRequest.from_dict(request.args.to_dict())
    current_app.logger.info("<get_shortname_refunds")
    refunds = EFTRefundService.get_shortname_refunds(request_data)
    current_app.logger.info("<get_shortname_refund")
    return jsonify(refunds), HTTPStatus.OK


@bp.route("/shortname-refund", methods=["POST", "OPTIONS"])
@cross_origin(origins="*")
@_jwt.has_one_of_roles([Role.EFT_REFUND.value, Role.EFT_REFUND_APPROVER.value])
def post_shortname_refund():
    """Create the Refund for the Shortname."""
    current_app.logger.info("<post_shortname_refund")
    request_json = request.get_json(silent=True)
    valid_format, errors = schema_utils.validate(request_json, "refund_shortname")
    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))
    try:
        response = EFTRefundService.create_shortname_refund(request_json)
        status = HTTPStatus.ACCEPTED
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug(">post_shortname_refund")
    return jsonify(response), status


@bp.route("/shortname-refund/<int:eft_refund_id>", methods=["PATCH"])
@cross_origin(origins="*")
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.EFT_REFUND_APPROVER.value])
def patch_shortname_refund(eft_refund_id: int):
    """Patch EFT short name link."""
    current_app.logger.info("<patch_eft_shortname_link")
    request_json = request.get_json()
    short_name_refund = EFTShortNameRefundPatchRequest.from_dict(request_json)
    try:
        if EFTRefundService.find_refund_by_id(eft_refund_id):
            response, status = (
                EFTRefundService.update_shortname_refund(eft_refund_id, short_name_refund),
                HTTPStatus.OK,
            )
        else:
            response, status = {}, HTTPStatus.NOT_FOUND
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug(">patch_eft_shortname_link")
    return jsonify(response), status
