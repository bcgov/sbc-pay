# Copyright © 2024 Province of British Columbia
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

from flask import Blueprint, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException
from pay_api.services import StatementSettings as StatementSettingsService
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import CHANGE_STATEMENT_SETTINGS, EDIT_ROLE
from pay_api.utils.endpoints_enums import EndpointEnum


bp = Blueprint('ACCOUNT_SETTINGS', __name__,
               url_prefix=f'{EndpointEnum.API_V1.value}/accounts/<string:account_id>/statements/settings')


@bp.route('', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET', 'POST'])
@_jwt.requires_auth
def get_account_statement_settings(account_id):
    """Get all statements records for an account."""
    current_app.logger.info('<get_account_statement_settings')

    # Check if user is authorized to perform this action
    check_auth(business_identifier=None, account_id=account_id, contains_role=EDIT_ROLE, is_premium=True)

    response, status = StatementSettingsService.find_by_account_id(account_id), HTTPStatus.OK
    current_app.logger.debug('>get_account_statement_settings')
    return jsonify(response), status


@bp.route('', methods=['POST'])
@cross_origin(origins='*')
@_jwt.requires_auth
def post_account_statement_settings(account_id):
    """Update the statement settings ."""
    current_app.logger.info('<post_account_statement_settings')
    request_json = request.get_json()
    current_app.logger.debug(request_json)
    frequency = request_json.get('frequency')

    # Check if user is authorized to perform this action
    check_auth(business_identifier=None, account_id=account_id,
               contains_role=CHANGE_STATEMENT_SETTINGS, is_premium=True)

    try:
        response, status = (
            StatementSettingsService.update_statement_settings(
                account_id, frequency
            ),
            HTTPStatus.OK,
        )
    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug('>post_account_statement_settings')
    return jsonify(response), status
