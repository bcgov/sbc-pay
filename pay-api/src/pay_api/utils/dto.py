from flask_restplus import Namespace, fields


class InvoiceDto:
    api = Namespace('invoices', description='Payment System - Invoices')

    invoice_line_item = api.model('InvoiceLineItem', {
        'name': fields.String(required=True, description='Line item name'),
        'description': fields.String(description='Line item description'),
        'amount': fields.String(required=True, description='Line item amount')
    })

    invoice_request = api.model('InvoiceRequest', {
        'entity_name': fields.String(required=True, description='Legal entity name'),
        'contact_first_name': fields.String(required=True, description='First Name of the contact person'),
        'contact_last_name': fields.String(required=True, description='Last Name of the contact person'),
        'address_line_1': fields.String(required=True, description='Address Line of entity'),
        'city': fields.String(required=True, description='City of entity'),
        'province': fields.String(required=True, description='Province'),
        'country': fields.String(required=True, description='Country'),
        'postal_code': fields.String(required=True, description='Postal Code'),
        'customer_site_id': fields.String(required=True, description='Customer Site Identifier'),
        'total': fields.String(required=True, description='Total amount for invoice'),
        'method_of_payment': fields.String(description='Method of Payment. CC/BCOL..', default='CC'),
        'lineItems': fields.List(fields.Nested(invoice_line_item))
    })




