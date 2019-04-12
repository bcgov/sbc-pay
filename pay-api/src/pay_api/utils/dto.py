# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Dto to hold the api definition and schema for Invoice endpoint."""
from flask_restplus import Namespace, fields


class InvoiceDto:
    """Class to hold the api definition and schema for Invoice endpoint."""

    api = Namespace('invoices', description='Payment System - Invoices')

    invoice_line_item = api.model('InvoiceLineItem', {
        'line_number': fields.String(required=True, description='Line number'),
        'line_type': fields.String(required=True, description='Line type, LINE/TAX'),
        'description': fields.String(description='Line item description'),
        'unit_price': fields.String(required=True, description='Line item amount'),
        'quantity': fields.String(required=True, description='Line item quantity')
    })

    invoice_request = api.model('InvoiceRequest', {
        'entity_name': fields.String(required=True, description='Entity name'),
        'entity_legal_name': fields.String(required=True, description='Legal entity name'),
        'site_name': fields.String(required=True, description='Site name'),


        'contact_first_name': fields.String(required=True, description='First Name of the contact person'),
        'contact_last_name': fields.String(required=True, description='Last Name of the contact person'),

        'address_line_1': fields.String(required=True, description='Address Line of entity'),
        'city': fields.String(required=True, description='City of entity'),
        'province': fields.String(required=True, description='Province'),
        # 'country': fields.String(required=True, description='Country'),
        'postal_code': fields.String(required=True, description='Postal Code'),

        'batch_source': fields.String(required=True, description='Batch Source ??'),
        'customer_transaction_type': fields.String(required=True, description='Customer Transaction Type ??'),

        'total': fields.Integer(required=True, description='Total amount for invoice'),
        'method_of_payment': fields.String(description='Method of Payment. CC/BCOL..', default='CC'),
        'lineItems': fields.List(fields.Nested(invoice_line_item))

    })
