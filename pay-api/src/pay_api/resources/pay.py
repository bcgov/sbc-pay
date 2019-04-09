from flask_restplus import Resource, Namespace

import opentracing
from flask_opentracing import FlaskTracing

API = Namespace('payments', description='Service - Payments')

tracer = opentracing.tracer
tracing = FlaskTracing(tracer)


@API.route("")
class Payment(Resource):

    @staticmethod
    @tracing.trace()
    def get():
        return {"message": "pay"}, 200

