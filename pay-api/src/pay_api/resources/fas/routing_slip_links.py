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
"""Resource for Routing slip Link endpoints."""
from http import HTTPStatus

from flask import current_app, jsonify, request
from flask_restx import Namespace, Resource, cors

from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services.fas import RoutingSlipService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.enums import Role
from pay_api.utils.errors import Error
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight

API = Namespace('fas', description='Fee Accounting System Links')


@cors_preflight('GET')
@API.route('/', methods=['GET', 'OPTIONS'])
class RoutingSlipLink(Resource):
    """Endpoint resource to deal with links in routing slips."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.FAS_VIEW.value])
    @_tracing.trace()
    def get(routing_slip_number: str):
        """Get routing slip links ;ie parent/child details."""
        current_app.logger.info('<RoutingSlipLink.get')
        response = RoutingSlipService.get_links(routing_slip_number)
        if response:
            status = HTTPStatus.OK
        else:
            response, status = {}, HTTPStatus.NO_CONTENT

        current_app.logger.debug('>RoutingSlipLink.get')
        return jsonify(response), status


@cors_preflight('POST')
@API.route('/', methods=['POST', 'OPTIONS'])
class RoutingSlipLinks(Resource):
    """Endpoint resource to deal with links in routing slips."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.FAS_EDIT.value])
    @_tracing.trace()
    def post():
        """Get routing slip links ;ie parent/child details."""
        current_app.logger.info('<RoutingSlipLink.post')
        try:
            request_json = request.get_json()
            valid_format, errors = schema_utils.validate(request_json, 'routing_slip_link_request')
            if not valid_format:
                return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

            response, status = RoutingSlipService.do_link(request_json.get('routingSlipNumber'),
                                                          request_json.get('parentRoutingSlipNumber')), HTTPStatus.OK
        except BusinessException as exception:
            return exception.response()

        current_app.logger.debug('>RoutingSlipLink.post')
        return jsonify(response), status
