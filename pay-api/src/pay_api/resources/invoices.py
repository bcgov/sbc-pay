# Copyright © 2022 Province of British Columbia
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
"""Resource for Invoice endpoints."""
from http import HTTPStatus

from flask import jsonify
from flask_restx import Namespace, Resource, cors

from pay_api.exceptions import BusinessException
from pay_api.services import InvoiceService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight


API = Namespace('invoices', description='Payment System - Payment Requests')


@cors_preflight(['GET'])
@API.route('', methods=['GET', 'OPTIONS'], doc={'deprecated': True})
class PaymentRequestInvoice(Resource):
    """Temporary endpoint to unblock teams who are using this endpoint."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.requires_auth
    @_tracing.trace()
    def get(invoice_id):
        """Subject to remove once the change has been notified to teams."""
        try:
            response = {
                'items': []
            }

            response['items'].append(InvoiceService.find_by_id(invoice_id).asdict())
        except BusinessException as exception:
            return exception.response()
        return jsonify(response), HTTPStatus.OK
