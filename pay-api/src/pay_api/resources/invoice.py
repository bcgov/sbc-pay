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
"""Meta information about the service.

Currently this only provides API versioning information
"""
import opentracing
from flask import request
from flask_opentracing import FlaskTracing
from flask_restplus import Resource, cors

from pay_api.services.paybc import PayBcService
from pay_api.utils.dto import InvoiceDto
from pay_api.utils.util import cors_preflight


API = InvoiceDto.api
INVOICE_REQUEST = InvoiceDto.invoice_request

TRACER = opentracing.tracer
TRACING = FlaskTracing(TRACER)

PAY_BC = PayBcService()


@cors_preflight('POST')
@API.route('')
class Invoice(Resource):
    """Endpoint resource to manage invoices."""

    @staticmethod
    @API.doc('Creates invoice in payment system')
    @API.expect(INVOICE_REQUEST, validate=True)
    @API.response(201, 'Invoice created successfully')
    @TRACING.trace()
    @cors.crossdomain(origin='*')
    def post():
        """Return a new invoice in the payment system."""
        request_json = request.get_json()
        user_type = 'basic'  # TODO We will get this from token, hard-coding for now
        if user_type == 'basic' and request_json.get('method_of_payment', None) == 'CC':
            print('Paying with credit card')
            PAY_BC.create_payment_records(request_json)
        return {'message': 'Invoice created successfully'}, 201
