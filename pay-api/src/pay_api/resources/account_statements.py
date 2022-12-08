# Copyright © 2022 Province of British Columbia
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

from flask import Response, current_app, jsonify, request
from flask_restx import Namespace, Resource, cors

from pay_api.services import Statement as StatementService
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import EDIT_ROLE
from pay_api.utils.enums import ContentType
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight


API = Namespace('accounts', description='Payment System - Statements')


@cors_preflight('GET')
@API.route('', methods=['GET', 'OPTIONS'])
class AccountStatements(Resource):
    """Endpoint resource for statements."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def get(account_id):
        """Get all statements records for an account."""
        current_app.logger.info('<AccountStatements.get')

        # Check if user is authorized to perform this action
        check_auth(business_identifier=None, account_id=account_id, contains_role=EDIT_ROLE, is_premium=True)

        page: int = int(request.args.get('page', '1'))
        limit: int = int(request.args.get('limit', '10'))

        response, status = StatementService.find_by_account_id(account_id, page, limit), HTTPStatus.OK
        current_app.logger.debug('>AccountStatements.get')
        return jsonify(response), status


@cors_preflight('GET')
@API.route('/<string:statement_id>', methods=['GET', 'OPTIONS'])
class AccountStatementReport(Resource):
    """Endpoint resource to generate account statement report."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def get(account_id: str, statement_id: str):
        """Create the statement report."""
        current_app.logger.info('<AccountStatementReport.post')
        response_content_type = request.headers.get('Accept', ContentType.PDF.value)

        # Check if user is authorized to perform this action
        auth = check_auth(business_identifier=None, account_id=account_id, contains_role=EDIT_ROLE, is_premium=True)

        report, report_name = StatementService.get_statement_report(statement_id=statement_id,
                                                                    content_type=response_content_type, auth=auth)
        response = Response(report, 200)
        response.headers.set('Content-Disposition', 'attachment', filename=report_name)
        response.headers.set('Content-Type', response_content_type)
        response.headers.set('Access-Control-Expose-Headers', 'Content-Disposition')
        return response
