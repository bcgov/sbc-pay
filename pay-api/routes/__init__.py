from flask_restplus import Api

api = Api(
    title='Payment API',
    version='1.0',
    description='The Core API for the Payment System',
    prefix='/api/v1')



from .ops import api as ops_api
from .pay import api as pay_api
from .refund import api as refund_api
from .status import api as status_api

api.add_namespace(ops_api, path='/ops')
api.add_namespace(pay_api, path='/pay')
api.add_namespace(refund_api, path='/refund')
api.add_namespace(status_api, path='/status')


