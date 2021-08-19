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

from flask import current_app, jsonify
from flask_restx import Namespace, Resource, cors

from pay_api.services.fas import RoutingSlipService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.enums import Role
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight


API = Namespace('fas', description='Fee Accounting System Links')


@cors_preflight('GET,PUT')
@API.route('/', methods=['GET', 'PUT', 'OPTIONS'])
class RoutingSlipLinks(Resource):
    """Endpoint resource to deal with links in routing slips."""

    @staticmethod
    @cors.crossdomain(origin='*')
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

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.FAS_EDIT.value])
    @_tracing.trace()
    def put(routing_slip_number: str):
        """Put routing slip."""
        current_app.logger.info('<RoutingSlips.put', routing_slip_number)
        # TODO
