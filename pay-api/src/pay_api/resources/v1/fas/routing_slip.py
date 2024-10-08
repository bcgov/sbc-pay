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

from flask import Blueprint, Response, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.exceptions import (
    BusinessException,
    ServiceUnavailableException,
    error_to_response,
)
from pay_api.schemas import utils as schema_utils
from pay_api.services.fas import RoutingSlipService, CommentService
from pay_api.utils.auth import jwt as _jwt  # noqa: I005
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import Role
from pay_api.utils.errors import Error

bp = Blueprint(
    "FAS_ROUTING_SLIPS",
    __name__,
    url_prefix=f"{EndpointEnum.API_V1.value}/fas/routing-slips",
)


@bp.route("", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
@_jwt.has_one_of_roles([Role.FAS_CREATE.value])
def post_routing_slip():
    """Create routing slip."""
    current_app.logger.info("<post_routing_slip")
    request_json = request.get_json()
    # Validate payload.
    valid_format, errors = schema_utils.validate(request_json, "routing_slip")
    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

    try:
        response, status = RoutingSlipService.create(request_json), HTTPStatus.CREATED
    except (BusinessException, ServiceUnavailableException) as exception:
        return exception.response()

    current_app.logger.debug(">post_routing_slip")
    return jsonify(response), status


@bp.route("/queries", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
@_jwt.has_one_of_roles([Role.FAS_SEARCH.value])
def post_search_routing_slips():
    """Get routing slips."""
    current_app.logger.info("<post_search_routing_slips")
    request_json = request.get_json()
    current_app.logger.debug(request_json)
    # validate the request
    valid_format, errors = schema_utils.validate(request_json, "routing_slip_search_request")
    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

    # if no page param , return all results
    return_all = not request_json.get("page", None)

    page: int = int(request_json.get("page", "1"))
    limit: int = int(request_json.get("limit", "10"))
    response, status = (
        RoutingSlipService.search(request_json, page, limit, return_all=return_all),
        HTTPStatus.OK,
    )
    current_app.logger.debug(">post_search_routing_slips")
    return jsonify(response), status


@bp.route("/<string:date>/reports", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
@_jwt.has_one_of_roles([Role.FAS_REPORTS.value])
def post_routing_slip_report(date: str):
    """Create routing slip report."""
    current_app.logger.info("<post_routing_slip_report")

    pdf, file_name = RoutingSlipService.create_daily_reports(date)

    response = Response(pdf, 201)
    response.headers.set("Content-Disposition", "attachment", filename=f"{file_name}.pdf")
    response.headers.set("Content-Type", "application/pdf")
    response.headers.set("Access-Control-Expose-Headers", "Content-Disposition")

    current_app.logger.debug(">post_routing_slip_report")
    return response


@bp.route("/<string:routing_slip_number>", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "PATCH"])
@_jwt.has_one_of_roles([Role.FAS_VIEW.value])
def get_routing_slip(routing_slip_number: str):
    """Get routing slip."""
    current_app.logger.info("<get_routing_slip")
    try:
        response = RoutingSlipService.validate_and_find_by_number(routing_slip_number)
        if response:
            status = HTTPStatus.OK
        else:
            response, status = {}, HTTPStatus.NO_CONTENT
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug(">get_routing_slip")
    return jsonify(response), status


@bp.route("/<string:routing_slip_number>", methods=["PATCH"])
@cross_origin(origins="*")
@_jwt.has_one_of_roles([Role.FAS_EDIT.value])
def patch_routing_slip(routing_slip_number: str):
    """Patch routing slip."""
    current_app.logger.info("<patch_routing_slip")
    try:
        response, status = (
            RoutingSlipService.update(
                routing_slip_number,
                request.args.get("action", None),
                request.get_json(),
            ),
            HTTPStatus.OK,
        )
    except (BusinessException, ServiceUnavailableException) as exception:
        return exception.response()

    current_app.logger.debug(">patch_routing_slip")
    return jsonify(response), status


@bp.route("/<string:routing_slip_number>/links", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
@_jwt.has_one_of_roles([Role.FAS_VIEW.value, Role.FAS_LINK.value])
def get_routing_slip_links(routing_slip_number: str):
    """Get routing slip links ;ie parent/child details."""
    current_app.logger.info("<get_routing_slip_links")
    response = RoutingSlipService.get_links(routing_slip_number)
    if response:
        status = HTTPStatus.OK
    else:
        response, status = {}, HTTPStatus.NO_CONTENT

    current_app.logger.debug(">get_routing_slip_links")
    return jsonify(response), status


@bp.route("/links", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
@_jwt.has_one_of_roles([Role.FAS_LINK.value])
def post_routing_slip_link():
    """Get routing slip links ;ie parent/child details."""
    current_app.logger.info("<post_routing_slip_link")

    request_json = request.get_json()
    valid_format, errors = schema_utils.validate(request_json, "routing_slip_link_request")
    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

    try:
        response, status = (
            RoutingSlipService.do_link(
                request_json.get("childRoutingSlipNumber"),
                request_json.get("parentRoutingSlipNumber"),
            ),
            HTTPStatus.OK,
        )
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug(">post_routing_slip_link")
    return jsonify(response), status


@bp.route("/<string:routing_slip_number>/comments", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "POST"])
@_jwt.has_one_of_roles([Role.FAS_VIEW.value])
def get_routing_slip_comments(routing_slip_number: str):
    """Get comments for a slip."""
    current_app.logger.info("<get_routing_slip_comments")
    try:
        response = CommentService.find_all_comments_for_a_routingslip(routing_slip_number)
        if response:
            status = HTTPStatus.OK
        else:
            response, status = {}, HTTPStatus.NO_CONTENT
    except (BusinessException, ServiceUnavailableException) as exception:
        return exception.response()

    current_app.logger.debug(">get_routing_slip_comments")
    return jsonify(response), status


@bp.route("/<string:routing_slip_number>/comments", methods=["POST"])
@cross_origin(origins="*")
@_jwt.has_one_of_roles([Role.FAS_VIEW.value])
def post_routing_slip_comment(routing_slip_number: str):
    """Create comment for a slip."""
    current_app.logger.info("<post_routing_slip_comment")
    response, status = None, None
    request_json = request.get_json()
    # Validate payload.
    try:
        valid_format, errors = schema_utils.validate(request_json, "comment")
        if valid_format:
            comment = request_json.get("comment")
        else:
            valid_format, errors = schema_utils.validate(request_json, "comment_bcrs_schema")
            if valid_format:
                comment = request_json.get("comment").get("comment")
            else:
                return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))
        if comment:
            response, status = (
                CommentService.create(comment_value=comment, rs_number=routing_slip_number),
                HTTPStatus.CREATED,
            )
    except (BusinessException, ServiceUnavailableException) as exception:
        return exception.response()

    current_app.logger.debug(">post_routing_slip_comment")
    return jsonify(response), status
