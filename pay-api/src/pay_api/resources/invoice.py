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
from flask_restplus import Namespace, Resource, cors

from pay_api.utils.util import cors_preflight
from pay_api.utils.dto import InvoiceDto

import opentracing
from flask_opentracing import FlaskTracing
from flask import request

from pay_api.services.paybc import PayBcService

API = InvoiceDto.api
invoice_request = InvoiceDto.invoice_request

tracer = opentracing.tracer
tracing = FlaskTracing(tracer)

pay_bc = PayBcService()


@cors_preflight('POST')
@API.route("")
class Invoice(Resource):
    """Meta information about the overall service."""

    @staticmethod
    @API.doc('Creates invoice in payment system')
    @API.expect(invoice_request, validate=True)
    @API.response(201, 'Invoice created successfully')
    @tracing.trace()
    @cors.crossdomain(origin='*')
    def post():
        request_json = request.get_json()
        user_type = 'basic'  # TODO We will get this from token, hard-coding for now
        if user_type == 'basic' and request_json.get('method_of_payment') == 'CC':
            print('Paying with credit card')
            pay_bc.create_payment_records(request_json)
        return {"message": "Invoice created succesfully"}, 201
