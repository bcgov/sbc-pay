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
from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import StatementRecipients
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.errors import Error
from pay_api.utils.constants import EDIT_ROLE, CHANGE_STATEMENT_SETTINGS
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight

API = Namespace('accounts', description='Payment System - Statements notifications')


@cors_preflight('GET,POST')
@API.route('', methods=['GET', 'POST', 'OPTIONS'])
class AccountStatementsNotifications(Resource):
    """Endpoint resource for account statements notifications."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def get(account_id):
        """Get all statements records for an account."""
        current_app.logger.info('<AccountStatementsNotifications.get')

        # Check if user is authorized to perform this action
        check_auth(business_identifier=None, account_id=account_id, contains_role=EDIT_ROLE, is_premium=True)
        statement_notification_details = StatementRecipients.find_statement_notification_details(account_id)
        response, status = statement_notification_details, HTTPStatus.OK
        current_app.logger.debug('>AccountStatementsNotifications.get')
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def post(account_id):
        """Update the statement settings ."""
        current_app.logger.info('<AccountStatementsNotifications.post')
        request_json = request.get_json()
        valid_format, errors = schema_utils.validate(request_json, 'statement_notification_request')
        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        current_app.logger.debug(request_json)
        # TODO add valid formatting
        # Check if user is authorized to perform this action
        check_auth(business_identifier=None, account_id=account_id, contains_role=CHANGE_STATEMENT_SETTINGS, is_premium=True)

        try:
            StatementRecipients.update_statement_notification_details(
                account_id, request_json)

        except BusinessException as exception:
            return exception.response()
        current_app.logger.debug('>AccountStatementsNotifications.post')
        return jsonify(None), HTTPStatus.CREATED
