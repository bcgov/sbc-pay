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

from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import StatementRecipients
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import CHANGE_STATEMENT_SETTINGS, EDIT_ROLE
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.errors import Error


bp = Blueprint(
    "ACCOUNT_NOTIFICATIONS",
    __name__,
    url_prefix=f"{EndpointEnum.API_V1.value}/accounts/<string:account_id>/statements/notifications",
)


@bp.route("", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "POST"])
@_jwt.requires_auth
def get_account_notifications(account_id):
    """Get all statements records for an account."""
    current_app.logger.info("<get_account_notifications")

    # Check if user is authorized to perform this action
    check_auth(
        business_identifier=None,
        account_id=account_id,
        contains_role=EDIT_ROLE,
        is_premium=True,
    )
    statement_notification_details = StatementRecipients.find_statement_notification_details(account_id)
    response, status = statement_notification_details, HTTPStatus.OK
    current_app.logger.debug(">get_account_notifications")
    return jsonify(response), status


@bp.route("", methods=["POST"])
@cross_origin(origins="*")
@_jwt.requires_auth
def post_account_notification(account_id):
    """Update the statement settings ."""
    current_app.logger.info("<post_account_notification")
    request_json = request.get_json()
    valid_format, errors = schema_utils.validate(request_json, "statement_notification_request")
    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

    current_app.logger.debug(request_json)

    # Check if user is authorized to perform this action
    check_auth(
        business_identifier=None,
        account_id=account_id,
        contains_role=CHANGE_STATEMENT_SETTINGS,
        is_premium=True,
    )

    try:
        StatementRecipients.update_statement_notification_details(account_id, request_json)

    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">post_account_notification")
    return jsonify(None), HTTPStatus.CREATED
