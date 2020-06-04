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
from http import HTTPStatus

from flask import jsonify, request
from flask_restplus import Namespace, Resource, cors

from pay_api.exceptions import BusinessException
from pay_api.services import FeeSchedule
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import DEFAULT_JURISDICTION
from pay_api.utils.enums import Role
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import convert_to_bool, cors_preflight
from pay_api.utils.user_context import get_auth_account_id
from pay_api.services.auth import check_auth
from pay_api.utils.constants import ALL_ALLOWED_ROLES
from pay_api.utils.util import get_str_by_path
from pay_api.utils.enums import AccountType

API = Namespace('fees', description='Payment System - Fees')


@cors_preflight('GET')
@API.route('/<string:corp_type>/<string:filing_type_code>', methods=['GET', 'OPTIONS'])
class Fee(Resource):
    """Endpoint resource to calculate fee."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @_tracing.trace()
    @_jwt.has_one_of_roles([Role.VIEWER.value, Role.EDITOR.value, Role.STAFF.value])
    def get(corp_type, filing_type_code):
        """Calculate the fee for the filing using the corp type/filing type and return fee."""
        date = request.args.get('date', datetime.today().strftime('%Y-%m-%d'))
        is_priority = convert_to_bool(request.args.get('priority', 'False'))
        is_future_effective = convert_to_bool(request.args.get('futureEffective', 'False'))
        jurisdiction = request.args.get('jurisdiction', DEFAULT_JURISDICTION)
        quantity = int(request.args.get('quantity', 1))
        waive_fees = False
        if _jwt.validate_roles([Role.STAFF.value]):
            waive_fees = convert_to_bool(request.args.get('waiveFees', 'False'))

        include_service_fees = False
        auth_account_id = get_auth_account_id()
        if auth_account_id and auth_account_id != '0':
            authorization = check_auth(business_identifier=None, account_id=auth_account_id,
                                       one_of_roles=ALL_ALLOWED_ROLES)
            include_service_fees = get_str_by_path(authorization, 'account/accountType') == AccountType.PREMIUM.value

        try:
            response, status = (
                FeeSchedule.find_by_corp_type_and_filing_type(
                    corp_type=corp_type,
                    filing_type_code=filing_type_code,
                    valid_date=date,
                    jurisdiction=jurisdiction,
                    is_priority=is_priority,
                    is_future_effective=is_future_effective,
                    waive_fees=waive_fees,
                    quantity=quantity,
                    include_service_fees=include_service_fees
                ).asdict(),
                HTTPStatus.OK,
            )
        except BusinessException as exception:
            return exception.response()
        return jsonify(response), status
