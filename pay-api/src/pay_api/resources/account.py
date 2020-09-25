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
from datetime import datetime
from http import HTTPStatus

from flask import Response, current_app, jsonify, request
from flask_restplus import Namespace, Resource, cors

from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import Payment
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import EDIT_ROLE
from pay_api.utils.enums import ContentType, Role
from pay_api.utils.errors import Error
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight

API = Namespace('accounts', description='Payment System - Accounts')


@cors_preflight('POST')
@API.route('', methods=['POST', 'OPTIONS'])
class Accounts(Resource):
    """Endpoint resource to create payment account."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_jwt.has_one_of_roles([Role.SYSTEM.value])
    def post():
        """Create the payment account records."""
        current_app.logger.info('<Account.post')
        request_json = request.get_json()
        current_app.logger.debug(request_json)
        # Validate the input request
        valid_format, errors = schema_utils.validate(request_json, 'account_info')

        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))
        try:
            response, status = PaymentAccountService.create(request_json).asdict(), HTTPStatus.CREATED
        except BusinessException as exception:
            return exception.response()
        current_app.logger.debug('>Account.post')
        return jsonify(response), status


@cors_preflight('PUT,GET')
@API.route('/<string:account_number>', methods=['PUT', 'GET', 'OPTIONS'])
class Account(Resource):
    """Endpoint resource to update and get payment account."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.SYSTEM.value])
    @_tracing.trace()
    def put(account_number: str):
        """Create the payment account records."""
        current_app.logger.info('<Account.post')
        request_json = request.get_json()
        current_app.logger.debug(request_json)
        # Validate the input request
        valid_format, errors = schema_utils.validate(request_json, 'account_info')

        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        response, status = PaymentAccountService.update(account_number, request_json).asdict(), HTTPStatus.OK
        current_app.logger.debug('>Account.post')
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.SYSTEM.value])
    @_tracing.trace()
    def get(account_number: str):
        """Create the payment account records."""
        current_app.logger.info('<Account.post')

        response, status = PaymentAccountService.find_by_auth_account_id(account_number).asdict(), HTTPStatus.OK
        current_app.logger.debug('>Account.post')
        return jsonify(response), status


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
        check_auth(business_identifier=None, account_id=account_number, contains_role=EDIT_ROLE, is_premium=True)

        page: int = int(request.args.get('page', '1'))
        limit: int = int(request.args.get('limit', '10'))
        response, status = Payment.search_purchase_history(account_number, request_json, page,
                                                           limit), HTTPStatus.OK
        current_app.logger.debug('>AccountPurchaseHistory.post')
        return jsonify(response), status


@cors_preflight('POST')
@API.route('/<string:account_number>/payments/reports', methods=['POST', 'OPTIONS'])
class AccountPurchaseReport(Resource):
    """Endpoint resource to create payment."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def post(account_number: str):
        """Create the payment records."""
        current_app.logger.info('<AccountPurchaseReport.post')
        response_content_type = request.headers.get('Accept', ContentType.PDF.value)
        request_json = request.get_json()
        current_app.logger.debug(request_json)
        # Validate the input request
        valid_format, errors = schema_utils.validate(request_json, 'purchase_history_request')
        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        report_name = 'bcregistry-transactions-{}'.format(datetime.now().strftime('%m-%d-%Y'))

        if response_content_type == ContentType.PDF.value:
            report_name = f'{report_name}.pdf'
        else:
            report_name = f'{report_name}.csv'

        # Check if user is authorized to perform this action
        check_auth(business_identifier=None, account_id=account_number, contains_role=EDIT_ROLE, is_premium=True)

        report = Payment.create_payment_report(account_number, request_json, response_content_type, report_name)
        response = Response(report, 201)
        response.headers.set('Content-Disposition', 'attachment', filename=report_name)
        response.headers.set('Content-Type', response_content_type)
        response.headers.set('Access-Control-Expose-Headers', 'Content-Disposition')
        return response
