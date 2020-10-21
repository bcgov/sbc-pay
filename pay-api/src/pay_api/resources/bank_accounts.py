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

from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import CFSService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.errors import Error
from pay_api.utils.util import cors_preflight

API = Namespace('bank_accounts', description='Payment System - Bank Accounts')


@cors_preflight('POST')
@API.route('', methods=['POST', 'OPTIONS'])
class BankAccounts(Resource):
    """Endpoint resource to deal with bank details."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    def post():
        """Create the payment account records."""
        current_app.logger.info('<BankAccounts.post')
        request_json = request.get_json()
        current_app.logger.debug(request_json)
        # Validate the input request
        valid_format, errors = schema_utils.validate(request_json, 'bank_accounts')

        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))
        try:
            response, status = CFSService.validate_bank_account(request_json), HTTPStatus.OK
        except BusinessException as exception:
            return exception.response()
        current_app.logger.debug('>Account.post')
        return jsonify(response), status
