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
"""Exposes all of the resource endpoints mounted in Flask-Blueprint style.

Uses restplus namespaces to mount individual api endpoints into the service.

All services have 2 defaults sets of endpoints:
 - ops
 - meta
That are used to expose operational health information about the service, and meta information.
"""
from flask import Blueprint
from flask_restplus import Api

from .bcol_profile import API as BCOL_API
from .fee import API as FEE_API
from .invoice import API as INVOICE_API
from .invoice_receipt import API as INVOICE_RECEIPT_API
from .meta import API as META_API
from .ops import API as OPS_API
from .paybc_invoice import API as PAYBC_INVOICE_API
from .payment import API as PAY_API
from .transaction import API as TRANSACTION_API
from .status import API as SERVICE_STATUS_API

__all__ = ('API_BLUEPRINT', 'OPS_BLUEPRINT')

# This will add the Authorize button to the swagger docs
# TODO oauth2 & openid may not yet be supported by restplus <- check on this
AUTHORIZATIONS = {'apikey': {'type': 'apiKey', 'in': 'header', 'name': 'Authorization'}}

OPS_BLUEPRINT = Blueprint('API_OPS', __name__, url_prefix='/ops')

API_OPS = Api(
    OPS_BLUEPRINT,
    title='Service OPS API',
    version='1.0',
    description='The Core API for the Payment System',
    security=['apikey'],
    authorizations=AUTHORIZATIONS,
)

API_OPS.add_namespace(OPS_API, path='/')

API_BLUEPRINT = Blueprint('API', __name__, url_prefix='/api/v1')

API = Api(
    API_BLUEPRINT,
    title='Payment API',
    version='1.0',
    description='The Core API for the Payment System',
    security=['apikey'],
    authorizations=AUTHORIZATIONS,
)

API.add_namespace(META_API, path='/meta')

API.add_namespace(PAYBC_INVOICE_API, path='/paybc/invoices')

API.add_namespace(PAY_API, path='/payments')
API.add_namespace(FEE_API, path='/fees')
API.add_namespace(TRANSACTION_API, path='/payments/<int:payment_id>/transactions')
API.add_namespace(INVOICE_API, path='/payments/<int:payment_id>/invoices')

API.add_namespace(INVOICE_RECEIPT_API, path='/payments/<int:payment_id>')

API.add_namespace(BCOL_API, path='/bcol/accounts/<string:account_id>/users/<string:user_id>')

API.add_namespace(SERVICE_STATUS_API, path='/status/<string:service_name>')
