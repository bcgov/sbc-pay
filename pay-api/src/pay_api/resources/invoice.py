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
"""Resource for Payment endpoints."""
from http import HTTPStatus

from flask import current_app, g, jsonify, request
from flask_restplus import Namespace, Resource, cors

from pay_api import jwt as _jwt
from pay_api.exceptions import BusinessException
from pay_api.schemas import utils as schema_utils
from pay_api.services import InvoiceService
from pay_api.utils.enums import Role
from pay_api.utils.util import cors_preflight


API = Namespace('invoices', description='Payment System - Invoices')


@cors_preflight(['GET', 'PUT'])
@API.route('', methods=['GET', 'OPTIONS'])
class Invoices(Resource):
    """Endpoint resource to get invoice."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.BASIC.value, Role.PREMIUM.value])
    def get(payment_id):
        """Get the Invoice records."""
        try:
            response, status = InvoiceService.get_invoice(payment_id), HTTPStatus.OK
        except BusinessException as exception:
            response, status = {'code': exception.code, 'message': exception.message}, exception.status
        return jsonify(response), status


@cors_preflight(['GET', 'PUT'])
@API.route('/<string:invoice_id>', methods=['GET', 'OPTIONS'])
class Invoice(Resource):
    """Endpoint resource to get invoice."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.BASIC.value, Role.PREMIUM.value])
    def get(payment_id, invoice_id):
        """Get the Invoice records."""
        try:
            response, status = InvoiceService.find_by_id(invoice_id).asdict(), HTTPStatus.OK
        except BusinessException as exception:
            response, status = {'code': exception.code, 'message': exception.message}, exception.status
        return jsonify(response), status

