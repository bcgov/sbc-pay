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
"""Resource for Invoice related endpoints."""

from http import HTTPStatus

from flask_restplus import Namespace, Resource

from pay_api.exceptions import BusinessException
from pay_api.services.bcol_service import BcolService
from pay_api.utils.trace import tracing as _tracing
from pay_api.utils.util import cors_preflight

API = Namespace('bcol profile', description='Payment System - BCOL Profiles')

BCOL_SERVICE = BcolService()


@cors_preflight(['GET', 'OPTIONS'])
@API.route('', methods=['GET', 'OPTIONS'])
class BcolProfile(Resource):
    """Endpoint resource to manage BCOL Accounts."""

    @staticmethod
    @API.response(200, 'OK')
    @_tracing.trace()
    def get(account_id: str, user_id: str):
        """Return the account details."""
        try:
            response, status = BCOL_SERVICE.query_profile(account_id, user_id), HTTPStatus.OK
        except BusinessException as exception:
            response, status = {'code': exception.code, 'message': exception.message}, exception.status
        return response, status
