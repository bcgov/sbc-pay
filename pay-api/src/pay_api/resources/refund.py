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
"""Resource for Refunds endpoints."""
from http import HTTPStatus

from flask import current_app, jsonify, request
from flask_restx import Namespace, Resource, cors

from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import RefundService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.enums import Role
from pay_api.utils.errors import Error
from pay_api.utils.util import cors_preflight

API = Namespace('refunds', description='Payment System - Refunds')


@cors_preflight('POST')
@API.route('/refunds', methods=['POST', 'OPTIONS'])
class Refund(Resource):
    """Endpoint resource to create refunds against invoices."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.SYSTEM.value, Role.CREATE_CREDITS.value, Role.FAS_REFUND.value])
    def post(invoice_id):
        """Create the Refund for the Invoice."""
        current_app.logger.info('<Refund.post')
        request_json = request.get_json(silent=True)
        try:
            valid_format, errors = schema_utils.validate(request_json, 'refund') if request_json else (True, None)
            if not valid_format:
                return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

            response = RefundService.create_refund(invoice_id, request_json)

        except BusinessException as exception:
            return exception.response()
        current_app.logger.debug('>Refund.post')
        return jsonify(response), HTTPStatus.ACCEPTED
