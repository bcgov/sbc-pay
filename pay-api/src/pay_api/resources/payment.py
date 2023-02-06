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

from flask import current_app, g, jsonify, request
from flask_restx import Namespace, Resource, cors

from pay_api.exceptions import error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import Payment as PaymentService
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import EDIT_ROLE, MAKE_PAYMENT, VIEW_ROLE
from pay_api.utils.enums import PaymentMethod, Role
from pay_api.utils.errors import Error
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight


API = Namespace('payment', description='Payment System - Payments')


@cors_preflight('GET,POST')
@API.route('', methods=['GET', 'POST', 'OPTIONS'])
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
        check_auth(business_identifier=None, account_id=account_id, one_of_roles=[MAKE_PAYMENT, EDIT_ROLE, VIEW_ROLE])
        page: int = int(request.args.get('page', '1'))
        limit: int = int(request.args.get('limit', '10'))
        status: str = request.args.get('status', None)
        response, status = PaymentService.search_account_payments(auth_account_id=account_id, status=status,
                                                                  page=page, limit=limit), HTTPStatus.OK
        current_app.logger.debug('>Payments.get')
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def post(account_id: str):
        """Create account payments."""
        current_app.logger.info('<Payments.post')
        # Check if user is authorized to perform this action
        check_auth(business_identifier=None, account_id=account_id, contains_role=MAKE_PAYMENT)
        # If it's a staff user, then create credits.
        if set([Role.STAFF.value, Role.CREATE_CREDITS.value]).issubset(set(g.jwt_oidc_token_info.get('roles'))):
            credit_request = request.get_json()
            # Valid payment payload.
            valid_format, errors = schema_utils.validate(credit_request, 'payment')
            if not valid_format:
                return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

            if credit_request.get('paymentMethod') in \
                    (PaymentMethod.EFT.value, PaymentMethod.WIRE.value, PaymentMethod.DRAWDOWN.value):
                response, status = PaymentService.create_payment_receipt(
                    auth_account_id=account_id,
                    credit_request=credit_request
                ).asdict(), HTTPStatus.CREATED
        else:
            is_retry_payment: bool = request.args.get('retryFailedPayment', 'false').lower() == 'true'

            response, status = PaymentService.create_account_payment(
                auth_account_id=account_id,
                is_retry_payment=is_retry_payment
            ).asdict(), HTTPStatus.CREATED

        current_app.logger.debug('>Payments.post')
        return jsonify(response), status
