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
"""Endpoints to check and manage payments."""
import opentracing
from flask_opentracing import FlaskTracing
from flask_restplus import Namespace, Resource


API = Namespace('payments', description='Service - Payments')

TRACER = opentracing.tracer
TRACING = FlaskTracing(TRACER)


@API.route('')
class Payment(Resource):
    """Payment endpoint resource."""

    @staticmethod
    @TRACING.trace()
    def get():
        """Get payment."""
        return {'message': 'pay'}, 200
