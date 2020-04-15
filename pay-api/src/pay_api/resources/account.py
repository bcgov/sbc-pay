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
"""Resource for Payment account."""
from http import HTTPStatus

from flask import current_app, jsonify, request
from flask_restplus import Namespace, Resource, cors

from pay_api.exceptions import error_to_response, BusinessException, ServiceUnavailableException
from pay_api.schemas import utils as schema_utils
from pay_api.services import Payment
from pay_api.services.auth import check_auth
from pay_api.utils.constants import EDIT_ROLE
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.errors import Error
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight

API = Namespace('accounts', description='Payment System - Purchase History')


@cors_preflight('POST')
@API.route('/<string:account_number>/payments/queries', methods=['POST', 'OPTIONS'])
class AccountPurchaseHistory(Resource):
    """Endpoint resource to create payment."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def post(account_number: str):
        """Create the payment records."""
        current_app.logger.info('<AccountPurchaseHistory.post')
        request_json = request.get_json()
        current_app.logger.debug(request_json)
        # Validate the input request
        valid_format, errors = schema_utils.validate(request_json, 'purchase_history_request')
        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        # Check if user is authorized to perform this action
        check_auth(business_identifier=None, account_id=account_number, contains_role=EDIT_ROLE)

        page: int = int(request.args.get('page', '1'))
        limit: int = int(request.args.get('limit', '10'))
        try:
            response, status = Payment.search_purchase_history(account_number, request_json, page,
                                                               limit), HTTPStatus.OK
        except (BusinessException, ServiceUnavailableException) as exception:
            return exception.response()
        current_app.logger.debug('>AccountPurchaseHistory.post')
        return jsonify(response), status
