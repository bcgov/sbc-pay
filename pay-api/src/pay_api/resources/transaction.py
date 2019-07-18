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
from flask import current_app, jsonify
from flask_restplus import Namespace, Resource, cors

from pay_api.exceptions import BusinessException
from pay_api.services import TransactionService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.enums import Role
from pay_api.utils.errors import Error
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight


API = Namespace('transactions', description='Payment System - Transactions')


@cors_preflight('POST,GET')
@API.route('', methods=['GET', 'POST', 'OPTIONS'])
class Transaction(Resource):
    """Endpoint resource to create transaction."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.BASIC.value, Role.PREMIUM.value])
    @_tracing.trace()
    def post(payment_id):
        """Create the Transaction records."""
        current_app.logger.info('<Transaction.post')
        redirect_uri = flask.request.args.get('redirect_uri')
        try:
            if not redirect_uri:
                raise BusinessException(Error.PAY007)

            response, status = TransactionService.create(payment_id, redirect_uri).asdict(), HTTPStatus.CREATED
        except BusinessException as exception:
            response, status = {'code': exception.code, 'message': exception.message}, exception.status
        current_app.logger.debug('>Transaction.post')
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.BASIC.value, Role.PREMIUM.value])
    @_tracing.trace()
    def get(payment_id):
        """Get all transaction records for a payment."""
        current_app.logger.info('<Transaction.get')
        response, status = TransactionService.find_by_payment_id(payment_id), HTTPStatus.OK
        current_app.logger.debug('>Transaction.get')
        return jsonify(response), status


@cors_preflight('PATCH,GET')
@API.route('/<uuid:transaction_id>', methods=['GET', 'PATCH', 'OPTIONS'])
class Transactions(Resource):
    """Endpoint resource to get transaction."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.BASIC.value, Role.PREMIUM.value])
    @_tracing.trace()
    def get(payment_id, transaction_id):
        """Get the Transaction record."""
        current_app.logger.info(
            f'<Transaction.get for payment : {payment_id}, and transaction {transaction_id}')
        try:
            response, status = TransactionService.find_by_id(payment_id,
                                                             transaction_id).asdict(), HTTPStatus.OK
        except BusinessException as exception:
            response, status = {'code': exception.code, 'message': exception.message}, exception.status
        current_app.logger.debug('>Transaction.get')
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.BASIC.value, Role.PREMIUM.value])
    @_tracing.trace()
    def patch(payment_id, transaction_id):
        """Update the transaction record by querying payment system."""
        current_app.logger.info(
            f'<Transaction.post for payment : {payment_id}, and transaction {transaction_id}')
        receipt_number = flask.request.args.get('receipt_number')
        try:
            response, status = TransactionService.update_transaction(payment_id, transaction_id,
                                                                     receipt_number).asdict(), HTTPStatus.OK
        except BusinessException as exception:
            response, status = {'code': exception.code, 'message': exception.message}, exception.status
        current_app.logger.debug('>Transaction.post')
        return jsonify(response), status
