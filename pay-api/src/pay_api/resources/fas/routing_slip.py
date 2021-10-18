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

from flask import Response, current_app, jsonify, request
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
    @_jwt.has_one_of_roles([Role.FAS_CREATE.value])
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


@cors_preflight('POST')
@API.route('/queries', methods=['POST', 'OPTIONS'])
class RoutingSlipSearch(Resource):
    """Endpoint resource to search for routing slips."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.FAS_SEARCH.value])
    @_tracing.trace()
    def post():
        """Get routing slips."""
        current_app.logger.info('<RoutingSlips.query.post')
        request_json = request.get_json()
        current_app.logger.debug(request_json)
        # validate the request
        valid_format, errors = schema_utils.validate(request_json, 'routing_slip_search_request')
        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        # if no page param , return all results
        if not request.args.get('page', None):
            return_all = True

        page: int = int(request.args.get('page', '1'))
        limit: int = int(request.args.get('limit', '10'))
        response, status = RoutingSlipService.search(request_json, page,
                                                     limit, return_all=return_all), HTTPStatus.OK
        current_app.logger.debug('>RoutingSlips.query.post')
        return jsonify(response), status


@cors_preflight('POST')
@API.route('/<string:date>/reports', methods=['POST', 'OPTIONS'])
class RoutingSlipReport(Resource):
    """Endpoint resource to generate report for routing slips."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.FAS_REPORTS.value])
    @_tracing.trace()
    def post(date: str):
        """Create routing slip report."""
        current_app.logger.info('<RoutingSlipReport.post')

        pdf, file_name = RoutingSlipService.create_daily_reports(date)

        response = Response(pdf, 201)
        response.headers.set('Content-Disposition', 'attachment', filename=f'{file_name}.pdf')
        response.headers.set('Content-Type', 'application/pdf')
        response.headers.set('Access-Control-Expose-Headers', 'Content-Disposition')

        current_app.logger.debug('>RoutingSlipReport.post')
        return response


@cors_preflight('GET,PATCH')
@API.route('/<string:routing_slip_number>', methods=['GET', 'PATCH', 'OPTIONS'])
class RoutingSlip(Resource):
    """Endpoint resource update and return routing slip by number."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.FAS_VIEW.value])
    @_tracing.trace()
    def get(routing_slip_number: str):
        """Get routing slip."""
        current_app.logger.info('<RoutingSlips.get')
        response = RoutingSlipService.find_by_number(routing_slip_number)
        if response:
            status = HTTPStatus.OK
        else:
            response, status = {}, HTTPStatus.NO_CONTENT

        current_app.logger.debug('>RoutingSlips.get')
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.FAS_EDIT.value])
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


@cors_preflight('GET')
@API.route('/<string:routing_slip_number>/links', methods=['GET', 'OPTIONS'])
class RoutingSlipLink(Resource):
    """Endpoint resource to deal with links in routing slips."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.FAS_VIEW.value, Role.FAS_LINK.value])
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
@API.route('/links', methods=['POST', 'OPTIONS'])
class RoutingSlipLinks(Resource):
    """Endpoint resource to deal with links in routing slips."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.FAS_LINK.value])
    @_tracing.trace()
    def post():
        """Get routing slip links ;ie parent/child details."""
        current_app.logger.info('<RoutingSlipLink.post')

        request_json = request.get_json()
        valid_format, errors = schema_utils.validate(request_json, 'routing_slip_link_request')
        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        try:
            response, status = RoutingSlipService.do_link(request_json.get('childRoutingSlipNumber'),
                                                          request_json.get('parentRoutingSlipNumber')), HTTPStatus.OK
        except BusinessException as exception:
            return exception.response()

        current_app.logger.debug('>RoutingSlipLink.post')
        return jsonify(response), status
