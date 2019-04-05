from flask_restplus import Resource, Namespace

import opentracing
from flask_opentracing import FlaskTracing
from service.paybc import PayBcService

api = Namespace('payments', description='Payment System - Pay')

tracer = opentracing.tracer
tracing = FlaskTracing(tracer)
pay_bc = PayBcService()

@api.route("")
class Payment(Resource):

    @staticmethod
    @tracing.trace()
    def get():
        return {"message": "pay"}, 200

    @staticmethod
    @api.doc('Creates payment related records in the payment system')
    #@api.expect(payment_request, validate=True)
    @api.response(201, 'Payment records created successfully')
    @tracing.trace()
    def post():
        user_type = 'basic'  # TODO We will get this from token, hard-coding for now
        method = 'CC'  # TODO We should get this from the paylod.
        if user_type == 'basic' and method == 'CC':
            print('Paying with credit card')
            pay_bc.create_invoice()
        return {"message": "pay"}, 200





