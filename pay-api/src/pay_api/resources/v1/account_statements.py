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
"""Resource for Payment account."""

from http import HTTPStatus

from flask import Blueprint, Response, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.services import Statement as StatementService
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import EDIT_ROLE
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import ContentType


bp = Blueprint('ACCOUNT_STATEMENTS', __name__,
               url_prefix=f'{EndpointEnum.API_V1.value}/accounts/<string:account_id>/statements')


@bp.route('', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET'])
@_jwt.requires_auth
def get_account_statements(account_id):
    """Get all statements records for an account."""
    current_app.logger.info('<get_account_statements')

    # Check if user is authorized to perform this action
    check_auth(business_identifier=None, account_id=account_id, contains_role=EDIT_ROLE)

    page: int = int(request.args.get('page', '1'))
    limit: int = int(request.args.get('limit', '10'))

    response, status = StatementService.find_by_account_id(account_id, page, limit), HTTPStatus.OK
    current_app.logger.debug('>get_account_statements')
    return jsonify(response), status


@bp.route('/<string:statement_id>', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET'])
@_jwt.requires_auth
def get_account_statement(account_id: str, statement_id: str):
    """Create the statement report."""
    current_app.logger.info('<get_account_statement')
    response_content_type = request.headers.get('Accept', ContentType.PDF.value)

    # Check if user is authorized to perform this action
    auth = check_auth(business_identifier=None, account_id=account_id, contains_role=EDIT_ROLE)

    report, report_name = StatementService.get_statement_report(statement_id=statement_id,
                                                                content_type=response_content_type, auth=auth)
    response = Response(report, 200)
    response.headers.set('Content-Disposition', 'attachment', filename=report_name)
    response.headers.set('Content-Type', response_content_type)
    response.headers.set('Access-Control-Expose-Headers', 'Content-Disposition')
    current_app.logger.info('>get_account_statement')
    return response


@bp.route('/summary', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET'])
@_jwt.requires_auth
def get_account_statement_summary(account_id: str):
    """Create the statement report."""
    current_app.logger.info('<get_account_statement_summary')
    check_auth(business_identifier=None, account_id=account_id, contains_role=EDIT_ROLE)
    response, status = StatementService.get_summary(account_id), HTTPStatus.OK
    current_app.logger.info('>get_account_statement_summary')
    return jsonify(response), status
