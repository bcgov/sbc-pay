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
"""Resource for Fee Calculation endpoints."""
from http import HTTPStatus

from flask import jsonify, request
from flask_restplus import Namespace, Resource, cors

from pay_api.exceptions import BusinessException
from pay_api.services import FeeSchedule
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.enums import Role
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight

API = Namespace('fee-schedules', description='Payment System - Fee Schedules')


@cors_preflight('GET')
@API.route('', methods=['GET', 'OPTIONS'])
class FeeSchedules(Resource):
    """Endpoint resource to calculate fee."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_tracing.trace()
    @_jwt.has_one_of_roles([Role.STAFF_ADMIN.value])
    def get():
        """Calculate the fee for the filing using the corp type/filing type and return fee."""
        try:
            corp_type = request.args.get('corp_type', None)
            filing_type = request.args.get('filing_type', None)
            response, status = (
                FeeSchedule.find_all(corp_type=corp_type, filing_type_code=filing_type),
                HTTPStatus.OK,
            )
        except BusinessException as exception:
            return exception.response()
        return jsonify(response), status
