from flask_restplus import Api

from jaeger_client import Config
from flask_opentracing import FlaskTracing


api = Api(
    title='Payment API',
    version='1.0',
    description='The Core API for the Payment System',
    prefix='/api/v1')


def init_tracer(service):
    config = Config(
        config={  # usually read from some yaml config
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
            'reporter_batch_size': 1,
        },
        service_name=service,
    )

    # this call also sets opentracing.tracer
    return config.initialize_tracer()


# this call also sets opentracing.tracer
tracer = init_tracer('pay_api')
FlaskTracing(tracer)

from .ops import api as ops_api
from .pay import api as pay_api
from .refund import api as refund_api
from .status import api as status_api

api.add_namespace(ops_api, path='/ops')
api.add_namespace(pay_api, path='/pay')
api.add_namespace(refund_api, path='/refund')
api.add_namespace(status_api, path='/status')


