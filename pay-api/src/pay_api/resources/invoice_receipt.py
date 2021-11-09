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
"""Resource for Transaction endpoints."""

from flask import Response, current_app, jsonify, request
from flask_restx import Namespace, Resource, cors

from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import ReceiptService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.errors import Error
from pay_api.utils.util import cors_preflight


API = Namespace('invoice-receipts', description='Payment System - Receipts')


@cors_preflight('POST,GET')
@API.route('/receipts', methods=['GET', 'POST', 'OPTIONS'])
class InvoiceReceipt(Resource):
    """Endpoint resource to create receipt.Use this endpoint when no invoice number is available."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    def post(invoice_id):
        """Create the Receipt for the Invoice."""
        request_json = request.get_json()
        current_app.logger.info('<Receipt.post')
        try:
            valid_format, errors = schema_utils.validate(request_json, 'payment_receipt_input')
            if not valid_format:
                return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

            pdf = ReceiptService.create_receipt(invoice_id, request_json)
            current_app.logger.info('<InvoiceReceipt received pdf')
            response = Response(pdf, 201)
            file_name = request_json.get('fileName')
            file_name = 'Coops-Filing' if not file_name else file_name
            response.headers.set('Content-Disposition', 'attachment', filename=f'{file_name}.pdf')
            response.headers.set('Content-Type', 'application/pdf')
            response.headers.set('Access-Control-Expose-Headers', 'Content-Disposition')
            return response

        except BusinessException as exception:
            return exception.response()
        current_app.logger.debug('>Transaction.post')
        return jsonify(response), 200

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    def get(invoice_id):
        """Return the receipt details."""
        current_app.logger.info('<Receipt.get')
        try:
            receipt_details = ReceiptService.get_receipt_details({}, invoice_id, skip_auth_check=False)
            receipt_details.pop('paymentMethodDescription', None)

        except BusinessException as exception:
            return exception.response()
        current_app.logger.debug('>Transaction.post')
        return jsonify(receipt_details), 200
