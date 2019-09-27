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
"""Resource for Payment endpoints."""
from http import HTTPStatus

from flask import current_app, g, jsonify, request
from flask_restplus import Namespace, Resource, cors

from pay_api.exceptions import BusinessException, ServiceUnavailableException
from pay_api.schemas import utils as schema_utils
from pay_api.services import PaymentService
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import EDIT_ROLE
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight


API = Namespace('payments', description='Payment System - Payments')


@cors_preflight('POST')
@API.route('', methods=['POST', 'OPTIONS'])
class Payment(Resource):
    """Endpoint resource to create payment."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def post():
        """Create the payment records."""
        current_app.logger.info('<Payment.post')
        request_json = request.get_json()

        # Validate the input request
        valid_format, errors = schema_utils.validate(request_json, 'payment_request')

        if not valid_format:
            return jsonify({'code': 'PAY999', 'message': schema_utils.serialize(errors)}), HTTPStatus.BAD_REQUEST

        # Check if user is authorized to perform this action
        check_auth(request_json.get('businessInfo').get('businessIdentifier'), _jwt, contains_role=EDIT_ROLE)

        try:
            response, status = PaymentService.create_payment(request_json, g.jwt_oidc_token_info), HTTPStatus.CREATED
        except BusinessException as exception:
            response, status = {'code': exception.code, 'message': exception.message}, exception.status
        except ServiceUnavailableException as exception:
            response, status = {'code': exception.status_code}, HTTPStatus.BAD_REQUEST
        current_app.logger.debug('>Payment.post')
        return jsonify(response), status


@cors_preflight(['GET', 'PUT'])
@API.route('/<int:payment_id>', methods=['GET', 'PUT', 'OPTIONS'])
class Payments(Resource):
    """Endpoint resource to create payment."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def get(payment_id):
        """Get the payment records."""
        try:
            response, status = PaymentService.get_payment(payment_id, _jwt), HTTPStatus.OK
        except BusinessException as exception:
            response, status = {'code': exception.code, 'message': exception.message}, exception.status
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def put(payment_id):
        """Update the payment records."""
        current_app.logger.info('<Payment.put')
        request_json = request.get_json()
        # Validate the input request
        valid_format, errors = schema_utils.validate(request_json, 'payment_request')
        if not valid_format:
            return jsonify({'code': 'PAY003', 'message': schema_utils.serialize(errors)}), HTTPStatus.BAD_REQUEST

        # Check if user is authorized to perform this action
        check_auth(request_json.get('businessInfo').get('businessIdentifier'), _jwt, one_of_roles=[EDIT_ROLE])

        try:
            response, status = (
                PaymentService.update_payment(
                    payment_id, request_json, g.jwt_oidc_token_info
                ),
                HTTPStatus.OK,
            )
        except BusinessException as exception:
            response, status = {'code': exception.code, 'message': exception.message}, exception.status
        except ServiceUnavailableException as exception:
            response, status = {'code': exception.status_code}, HTTPStatus.BAD_REQUEST
        current_app.logger.debug('>Payment.put')
        return jsonify(response), status
