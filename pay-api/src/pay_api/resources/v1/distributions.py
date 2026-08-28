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
"""Resource for Distribution endpoints."""

from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import DistributionCode as DistributionCodeService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import Role
from pay_api.utils.errors import Error

bp = Blueprint(
    "DISTRIBUTIONS",
    __name__,
    url_prefix=f"{EndpointEnum.API_V1.value}/fees/distributions",
)


@bp.route("/<int:distribution_code_id>", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "PUT"])
@_jwt.has_one_of_roles([Role.MANAGE_GL_CODES.value])
def get_fee_distribution(distribution_code_id: int):
    """Return distribution by provided id."""
    try:
        response, status = (
            DistributionCodeService.find_by_id(distribution_code_id),
            HTTPStatus.OK,
        )

    except BusinessException as exception:
        return exception.response()
    return jsonify(response), status


@bp.route("/<int:distribution_code_id>", methods=["PUT"])
@cross_origin(origins="*")
@_jwt.has_one_of_roles([Role.MANAGE_GL_CODES.value])
def put_fee_distribution(distribution_code_id: int):
    """Update distribution from the payload."""
    request_json = request.get_json()

    valid_format, errors = schema_utils.validate(request_json, "distribution_code")
    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

    try:
        response, status = (
            DistributionCodeService.save_or_update(request_json, distribution_code_id),
            HTTPStatus.OK,
        )
    except BusinessException as exception:
        return exception.response()
    return jsonify(response), status


@bp.route("", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "POST"])
@_jwt.has_one_of_roles([Role.MANAGE_GL_CODES.value])
def get_fee_distributions():
    """Return all distributions."""
    try:
        response, status = (
            DistributionCodeService.find_all(),
            HTTPStatus.OK,
        )

    except BusinessException as exception:
        return exception.response()
    return jsonify(response), status


@bp.route("", methods=["POST"])
@cross_origin(origins="*")
@_jwt.has_one_of_roles([Role.MANAGE_GL_CODES.value])
def post_fee_distribution():
    """Create a new distribution from the payload."""
    request_json = request.get_json()

    valid_format, errors = schema_utils.validate(request_json, "distribution_code")
    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

    try:
        response, status = (
            DistributionCodeService.save_or_update(request_json),
            HTTPStatus.CREATED,
        )
    except BusinessException as exception:
        return exception.response()
    return jsonify(response), status


@bp.route("/<int:distribution_code_id>/schedules", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "POST"])
@_jwt.has_one_of_roles([Role.MANAGE_GL_CODES.value])
def get_fee_distribution_schedules(distribution_code_id: int):
    """Return all fee schedules linked to the distribution."""
    try:
        response, status = (
            DistributionCodeService.find_fee_schedules_by_distribution_id(distribution_code_id),
            HTTPStatus.OK,
        )

    except BusinessException as exception:
        return exception.response()
    return jsonify(response), status


@bp.route("/<int:distribution_code_id>/schedules", methods=["POST"])
@cross_origin(origins="*")
@_jwt.has_one_of_roles([Role.MANAGE_GL_CODES.value])
def post_fee_distribution_schedule(distribution_code_id: int):
    """Create link between distribution and fee schedule."""
    request_json = request.get_json()

    try:
        DistributionCodeService.create_link(request_json, distribution_code_id)
    except BusinessException as exception:
        return exception.response()
    return jsonify(None), HTTPStatus.CREATED
