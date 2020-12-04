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
"""Resource for Payment Request/Invoice endpoints."""
from http import HTTPStatus

from flask import current_app, jsonify, request
from flask_restplus import Namespace, Resource, cors

from pay_api.exceptions import error_to_response, BusinessException, ServiceUnavailableException
from pay_api.schemas import utils as schema_utils
from pay_api.services import PaymentService, InvoiceService
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import EDIT_ROLE
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.errors import Error
from pay_api.utils.util import cors_preflight, get_str_by_path


API = Namespace('invoice', description='Payment System - Invoices')


@cors_preflight('POST')
@API.route('', methods=['POST', 'OPTIONS'])
class Invoice(Resource):
    """Endpoint resource to create payment."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def post():
        """Create the payment request records."""
        current_app.logger.info('<Payment.post')
        request_json = request.get_json()
        current_app.logger.debug(request_json)
        # Validate the input request
        valid_format, errors = schema_utils.validate(request_json, 'payment_request')

        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        # Check if user is authorized to perform this action
        business_identifier = get_str_by_path(request_json, 'businessInfo/businessIdentifier')
        corp_type_code = get_str_by_path(request_json, 'businessInfo/corpType')

        authorization = check_auth(business_identifier=business_identifier, corp_type_code=corp_type_code,
                                   contains_role=EDIT_ROLE)
        try:
            response, status = PaymentService.create_invoice(request_json, authorization), HTTPStatus.CREATED
        except (BusinessException, ServiceUnavailableException) as exception:
            return exception.response()
        current_app.logger.debug('>Payment.post')
        return jsonify(response), status


@cors_preflight(['GET', 'PUT', 'DELETE', 'PATCH'])
@API.route('/<int:invoice_id>', methods=['GET', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
class Invoices(Resource):
    """Endpoint resource to create payment request."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def get(invoice_id):
        """Get the invoice records."""
        try:
            response, status = InvoiceService.find_by_id(invoice_id).asdict(), HTTPStatus.OK
        except BusinessException as exception:
            return exception.response()
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def delete(invoice_id):
        """Soft delete the invoice records."""
        current_app.logger.info('<Payment.delete')

        try:
            PaymentService.accept_delete(invoice_id)

            response, status = None, HTTPStatus.ACCEPTED

        except BusinessException as exception:
            return exception.response()

        current_app.logger.debug('>Payment.delete')
        return jsonify(response), status

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def patch(invoice_id: int = None):
        """Update the payment method for an online banking ."""
        current_app.logger.info('<Invoice.patch for invoice : %s', invoice_id)

        request_json = request.get_json()
        current_app.logger.debug(request_json)
        # Validate the input request
        valid_format, errors = schema_utils.validate(request_json, 'payment_info')

        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        try:
            response, status = PaymentService.update_invoice(invoice_id,
                                                             request_json).asdict(), HTTPStatus.OK
        except BusinessException as exception:
            return exception.response()
        current_app.logger.debug('>Transaction.post')
        return jsonify(response), status
