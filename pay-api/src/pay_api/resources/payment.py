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
"""Resource for Account payments endpoints."""
from http import HTTPStatus

from flask import current_app, jsonify, request
from flask_restplus import Namespace, Resource, cors

from pay_api.services import Payment as PaymentService
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import EDIT_ROLE
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight

API = Namespace('payment', description='Payment System - Payments')


@cors_preflight('GET')
@API.route('', methods=['GET', 'OPTIONS'])
class Payments(Resource):
    """Endpoint resource to create and return an account payments."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def get(account_id: str):
        """Get account payments."""
        current_app.logger.info('<Payments.get')
        # Check if user is authorized to perform this action
        check_auth(business_identifier=None, account_id=account_id, contains_role=EDIT_ROLE)
        page: int = int(request.args.get('page', '1'))
        limit: int = int(request.args.get('limit', '10'))
        status: str = request.args.get('status', None)
        response, status = PaymentService.search_account_payments(auth_account_id=account_id, status=status,
                                                                  page=page, limit=limit), HTTPStatus.OK
        current_app.logger.debug('>Account.get')
        return jsonify(response), status
