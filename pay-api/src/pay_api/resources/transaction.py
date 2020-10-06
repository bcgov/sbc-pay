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

from flask import current_app, jsonify, request
from flask_restplus import Namespace, Resource, cors

from pay_api.exceptions import error_to_response, BusinessException
from pay_api.schemas import utils as schema_utils
from pay_api.services import TransactionService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight
from pay_api.utils.errors import Error


API = Namespace('transactions', description='Payment System - Transactions')


@cors_preflight('POST,GET')
@API.route('', methods=['GET', 'POST', 'OPTIONS'])
class Transaction(Resource):
    """Endpoint resource to create transaction."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_tracing.trace()
    def post(invoice_id):
        """Create the Transaction records."""
        current_app.logger.info('<Transaction.post')
        request_json = request.get_json()

        # Validate the input request
        valid_format, errors = schema_utils.validate(request_json, 'transaction_request')

        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        try:
            response, status = TransactionService.create(invoice_id, request_json).asdict(), HTTPStatus.CREATED
        except BusinessException as exception:
            return exception.response()
        current_app.logger.debug('>Transaction.post')
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def get(invoice_id):
        """Get all transaction records for a invoice."""
        current_app.logger.info('<Transaction.get')
        response, status = TransactionService.find_by_invoice_id(invoice_id), HTTPStatus.OK
        current_app.logger.debug('>Transaction.get')
        return jsonify(response), status


@cors_preflight('PATCH,GET')
@API.route('/<uuid:transaction_id>', methods=['GET', 'PATCH', 'OPTIONS'])
class Transactions(Resource):
    """Endpoint resource to get transaction."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def get(invoice_id, transaction_id):
        """Get the Transaction record."""
        current_app.logger.info(
            f'<Transaction.get for invoice : {invoice_id}, and transaction {transaction_id}')
        try:
            response, status = TransactionService.find_by_id(transaction_id).asdict(), HTTPStatus.OK
        except BusinessException as exception:
            return exception.response()
        current_app.logger.debug('>Transaction.get')
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_tracing.trace()
    def patch(invoice_id, transaction_id):
        """Update the transaction record by querying payment system."""
        current_app.logger.info(
            f'<Transaction.post for payment : {invoice_id}, and transaction {transaction_id}')
        pay_response_url: str = request.get_json().get('payResponseUrl', None)

        try:
            response, status = TransactionService.update_transaction(transaction_id,
                                                                     pay_response_url).asdict(), HTTPStatus.OK
        except BusinessException as exception:
            return exception.response()
        current_app.logger.debug('>Transaction.post')
        return jsonify(response), status
