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
"""Resource for Transaction endpoints."""
from http import HTTPStatus
import flask
from flask import current_app, g, jsonify, request
from flask_restplus import Namespace, Resource, cors

from pay_api import jwt as _jwt
from pay_api.exceptions import BusinessException
from pay_api.services import TransactionService
from pay_api.utils.enums import Role
from pay_api.utils.util import cors_preflight
from pay_api.utils.errors import Error

API = Namespace('transactions', description='Payment System - Transactions')


@cors_preflight('POST')
@API.route('', methods=['POST', 'OPTIONS'])
class Transaction(Resource):
    """Endpoint resource to create transaction."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.BASIC.value, Role.PREMIUM.value])
    def post(payment_identifier):
        """Create the Transaction records."""
        current_app.logger.info('<Transaction.post')
        redirect_uri = flask.request.args.get('request_uri')
        try:
            if not redirect_uri:
                raise BusinessException(Error.PAY007)

            response, status = TransactionService.create(payment_identifier, redirect_uri).asdict(), HTTPStatus.CREATED
        except BusinessException as exception:
            response, status = {'code': exception.code, 'message': exception.message}, exception.status
        current_app.logger.debug('>Transaction.post')
        return jsonify(response), status


@cors_preflight('GET')
@API.route('', methods=['GET', 'OPTIONS'])
class Transactions(Resource):
    """Endpoint resource to get transaction."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.BASIC.value, Role.PREMIUM.value])
    def get(payment_identifier):
        """Get the Transaction record."""
        current_app.logger.info('<Transaction.get')
        try:
            response, status = TransactionService.find_by_id(payment_identifier).asdict(), HTTPStatus.CREATED
        except BusinessException as exception:
            response, status = {'code': exception.code, 'message': exception.message}, exception.status
        current_app.logger.debug('>Transaction.get')
        return jsonify(response), status
