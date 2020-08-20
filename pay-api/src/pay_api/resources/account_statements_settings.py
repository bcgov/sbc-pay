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
"""Resource for Statement Settings."""
from http import HTTPStatus

from flask import current_app, jsonify, request
from flask_restplus import Namespace, Resource, cors
from pay_api.exceptions import BusinessException
from pay_api.services import StatementSettings as StatementSettingsService
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import EDIT_ROLE
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight

API = Namespace('accounts', description='Payment System - Statements Settings')


@cors_preflight('GET,PUT')
@API.route('', methods=['GET', 'PUT', 'OPTIONS'])
class AccountStatementsSettings(Resource):
    """Endpoint resource for statements."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def get(account_id):
        """Get all statements records for an account."""
        current_app.logger.info('<AccountStatementsSettings.get')

        # Check if user is authorized to perform this action
        check_auth(business_identifier=None, account_id=account_id, contains_role=EDIT_ROLE, is_premium=True)

        response, status = StatementSettingsService.find_by_account_id(account_id), HTTPStatus.OK
        current_app.logger.debug('>AccountStatementsSettings.get')
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def put(account_id):
        """Update the statement settings ."""
        current_app.logger.info('<AccountStatementsSettings.put')
        request_json = request.get_json()
        current_app.logger.debug(request_json)
        # TODO add valid formatting
        frequency = request_json.get('frequency')
        # Check if user is authorized to perform this action
        check_auth(business_identifier=None, account_id=account_id, contains_role=EDIT_ROLE, is_premium=True)

        try:
            response, status = (
                StatementSettingsService.update_statement_settings(
                    account_id, frequency
                ),
                HTTPStatus.OK,
            )
        except BusinessException as exception:
            return exception.response()
        current_app.logger.debug('>Payment.put')
        return jsonify(response), status
