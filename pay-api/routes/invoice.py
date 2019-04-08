from flask_restplus import Resource
from util.dto import InvoiceDto
from flask import request

import opentracing
from flask_opentracing import FlaskTracing
import logging


from service.paybc import PayBcService

tracer = opentracing.tracer
tracing = FlaskTracing(tracer)
pay_bc = PayBcService()
api = InvoiceDto.api
invoice_request = InvoiceDto.invoice_request


@api.route("")
class Invoice(Resource):
    @staticmethod
    @api.doc('Creates invoice in payment system')
    @api.expect(invoice_request, validate=True)
    @api.response(201, 'Invoice created successfully')
    @tracing.trace()
    def post():
        request_json = request.get_json()
        user_type = 'basic'  # TODO We will get this from token, hard-coding for now
        if user_type == 'basic' and request_json.get('method_of_payment') == 'CC':
            print('Paying with credit card')
            pay_bc.create_payment_records(request_json)
        return {"message": "Invoice created succesfully"}, 201





