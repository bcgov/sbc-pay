# Copyright © 2019 Province of British Columbia
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

from flask import current_app, jsonify, request
from flask_restx import Namespace, Resource, cors

from pay_api.exceptions import BusinessException, ServiceUnavailableException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services.fas import RoutingSlipService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.enums import Role
from pay_api.utils.errors import Error
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight


API = Namespace('fas', description='Fee Accounting System')


@cors_preflight('GET,POST')
@API.route('', methods=['GET', 'POST', 'OPTIONS'])
class RoutingSlips(Resource):
    """Endpoint resource to create and return routing slips."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.FAS_USER.value])
    @_tracing.trace()
    def get():
        """Get routing slips."""
        current_app.logger.info('<RoutingSlips.get')
        page: int = int(request.args.get('page', '1'))
        limit: int = int(request.args.get('limit', '10'))
        status: str = request.args.get('status', None)
        response, status = RoutingSlipService.search(status=status, page=page, limit=limit), HTTPStatus.OK
        current_app.logger.debug('>RoutingSlips.get')
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.FAS_EDITOR.value])
    @_tracing.trace()
    def post():
        """Create routing slip."""
        current_app.logger.info('<RoutingSlips.post')
        request_json = request.get_json()
        # Validate payload.
        valid_format, errors = schema_utils.validate(request_json, 'routing_slip')
        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        try:
            response, status = RoutingSlipService.create(request_json), HTTPStatus.CREATED
        except (BusinessException, ServiceUnavailableException) as exception:
            return exception.response()

        current_app.logger.debug('>RoutingSlips.post')
        return jsonify(response), status


@cors_preflight('GET,PATCH')
@API.route('/<string:routing_slip_number>', methods=['GET', 'PATCH', 'OPTIONS'])
class RoutingSlip(Resource):
    """Endpoint resource to create and return routing slips."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.FAS_USER.value])
    @_tracing.trace()
    def get(routing_slip_number: str):
        """Get routing slip."""
        current_app.logger.info('<RoutingSlips.get')
        response = RoutingSlipService.find_by_number(routing_slip_number)
        if response:
            status = HTTPStatus.OK
        else:
            response, status = {}, HTTPStatus.NOT_FOUND

        current_app.logger.debug('>RoutingSlips.get')
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.FAS_EDITOR.value])
    @_tracing.trace()
    def patch(routing_slip_number: str):
        """Patch routing slip."""
        current_app.logger.info('<RoutingSlips.patch')
        try:
            response, status = RoutingSlipService.update(
                routing_slip_number, request.args.get('action', None), request.get_json()), HTTPStatus.OK
        except (BusinessException, ServiceUnavailableException) as exception:
            return exception.response()

        current_app.logger.debug('>RoutingSlips.patch')
        return jsonify(response), status
