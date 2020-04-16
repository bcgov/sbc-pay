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

from flask import request
from flask_restplus import Namespace, Resource

from bcol_api.exceptions import BusinessException
from bcol_api.exceptions import error_to_response
from bcol_api.schemas import utils as schema_utils
from bcol_api.services.bcol_profile import BcolProfile as BcolProfileService
from bcol_api.utils.auth import jwt as _jwt
from bcol_api.utils.errors import Error
from bcol_api.utils.trace import tracing as _tracing
from bcol_api.utils.util import cors_preflight


API = Namespace('bcol profile', description='Payment System - BCOL Profiles')


@cors_preflight(['POST', 'OPTIONS'])
@API.route('', methods=['POST', 'OPTIONS'])
class BcolProfile(Resource):
    """Endpoint resource to manage BCOL Accounts."""

    @staticmethod
    @_tracing.trace()
    @_jwt.requires_auth
    def post():
        """Return the account details."""
        try:
            req_json = request.get_json()
            # Validate the input request
            valid_format = schema_utils.validate(req_json, 'accounts_request')
            if not valid_format[0]:
                return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(valid_format[1]))

            response, status = BcolProfileService().query_profile(req_json.get('userId'),
                                                                  req_json.get('password')), HTTPStatus.OK
        except BusinessException as exception:
            return exception.response()
        return response, status
