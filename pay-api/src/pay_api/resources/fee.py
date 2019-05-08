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
from datetime import datetime

from flask import jsonify, request
from flask_restplus import Namespace, Resource, cors

from pay_api import jwt as _jwt
from pay_api.exceptions import BusinessException
from pay_api.services.fee_schedule import FeeSchedule
from pay_api.utils.constants import DEFAULT_JURISDICTION
from pay_api.utils.roles import Role
from pay_api.utils.util import cors_preflight


API = Namespace('fees', description='Payment System - Fees')


@cors_preflight('GET')
@API.route('/<string:corp_type>/<string:filing_type_code>')
class Fee(Resource):
    """Endpoint resource to calculate fee."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_jwt.has_one_of_roles([Role.BASIC.value, Role.PREMIUM.value])
    def get(corp_type, filing_type_code):
        """Calculate the fee for the filing using the corp type/filing type and return fee."""
        date = request.args.get('date', datetime.today().strftime('%Y-%m-%d'))
        jurisdiction = request.args.get('jurisdiction', DEFAULT_JURISDICTION)
        priority = request.args.get('priority', False)
        try:
            response, status = FeeSchedule.find_by_corp_type_and_filing_type(
                corp_type=corp_type,
                filing_type_code=filing_type_code,
                valid_date=date,
                jurisdiction=jurisdiction,
                priority=priority).asdict(), 200
        except BusinessException as exception:
            response, status = {'code': exception.code, 'message': exception.message}, exception.status
        return jsonify(response), status
