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
"""Resource for Invoice related endpoints."""
from flask import current_app, request
from flask_restplus import Namespace, Resource

from pay_api import tracing as _tracing
from pay_api.services.paybc import PayBcService
from pay_api.utils.util import cors_preflight


API = Namespace('invoices', description='Payment System - Invoices')

PAY_BC_SERVICE = PayBcService()


@cors_preflight(['POST', 'OPTIONS'])
@API.route('')
class Invoice(Resource):
    """Endpoint resource to manage invoices."""

    @staticmethod
    @API.doc('Creates invoice in payment system')
    @API.response(201, 'Invoice created successfully')
    @_tracing.trace()
    def post():
        """Return a new invoice in the payment system."""
        request_json = request.get_json()
        user_type = 'basic'  # TODO We will get this from token, hard-coding for now
        if user_type == 'basic' and request_json.get('method_of_payment', None) == 'CC':
            current_app.logger.debug('Paying with credit card')
            invoice_response = PAY_BC_SERVICE.create_payment_records(request_json)
            response_json = {
                'paybc_reference_number': invoice_response.get('pbc_ref_number', None),
                'invoice_number': invoice_response.get('invoice_number', None),
            }
        else:
            response_json = {'message': 'Invoice created successfully'}
        return response_json, 201
