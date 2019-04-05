from flask_restplus import Resource, Namespace

import opentracing
from flask_opentracing import FlaskTracing

api = Namespace('payments', description='Payment System - Pay')

tracer = opentracing.tracer
tracing = FlaskTracing(tracer)


@api.route("")
class Payment(Resource):

    @staticmethod
    @tracing.trace()
    def get():
        return {"message": "pay"}, 200

