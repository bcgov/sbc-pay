# Copyright © 2022 Province of British Columbia
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

from flask import jsonify, request
from flask_restx import Namespace, Resource, cors

from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import DistributionCode as DistributionCodeService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.enums import Role
from pay_api.utils.errors import Error
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight


API = Namespace('fees-distributions', description='Payment System - Distributions')


@cors_preflight('GET, POST')
@API.route('', methods=['GET', 'POST', 'OPTIONS'])
class Distributions(Resource):
    """Endpoint resource to get and post distribution."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_tracing.trace()
    @_jwt.has_one_of_roles([Role.MANAGE_GL_CODES.value])
    def get():
        """Return all distributions."""
        try:
            response, status = (
                DistributionCodeService.find_all(),
                HTTPStatus.OK,
            )

        except BusinessException as exception:
            return exception.response()
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_tracing.trace()
    @_jwt.has_one_of_roles([Role.MANAGE_GL_CODES.value])
    def post():
        """Create a new distribution from the payload."""
        request_json = request.get_json()

        valid_format, errors = schema_utils.validate(request_json, 'distribution_code')
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


@cors_preflight(['GET', 'PUT'])
@API.route('/<int:distribution_code_id>', methods=['GET', 'PUT', 'OPTIONS'])
class Distribution(Resource):
    """Endpoint resource to handle distribution."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_tracing.trace()
    @_jwt.has_one_of_roles([Role.MANAGE_GL_CODES.value])
    def get(distribution_code_id: int):
        """Return distribution by provided id."""
        try:
            response, status = (
                DistributionCodeService.find_by_id(distribution_code_id),
                HTTPStatus.OK,
            )

        except BusinessException as exception:
            return exception.response()
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_tracing.trace()
    @_jwt.has_one_of_roles([Role.MANAGE_GL_CODES.value])
    def put(distribution_code_id: int):
        """Update distribution from the payload."""
        request_json = request.get_json()

        valid_format, errors = schema_utils.validate(request_json, 'distribution_code')
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


@cors_preflight(['GET', 'POST'])
@API.route('/<int:distribution_code_id>/schedules', methods=['GET', 'POST', 'OPTIONS'])
class DistributionSchedules(Resource):
    """Endpoint resource to handle Distribution Schedules."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_tracing.trace()
    @_jwt.has_one_of_roles([Role.MANAGE_GL_CODES.value])
    def get(distribution_code_id: int):
        """Return all fee schedules linked to the distribution."""
        try:
            response, status = (
                DistributionCodeService.find_fee_schedules_by_distribution_id(distribution_code_id),
                HTTPStatus.OK,
            )

        except BusinessException as exception:
            return exception.response()
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_tracing.trace()
    @_jwt.has_one_of_roles([Role.MANAGE_GL_CODES.value])
    def post(distribution_code_id: int):
        """Create link between distribution and fee schedule."""
        request_json = request.get_json()

        try:
            DistributionCodeService.create_link(request_json, distribution_code_id)
        except BusinessException as exception:
            return exception.response()
        return jsonify(None), HTTPStatus.CREATED
