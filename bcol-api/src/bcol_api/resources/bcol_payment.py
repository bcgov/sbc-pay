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
"""Resource for BCOL accounts related operations."""

from http import HTTPStatus

from flask import abort, current_app, request
from flask_restx import Namespace, Resource, cors

from bcol_api.exceptions import BusinessException, PaymentException, error_to_response
from bcol_api.schemas import utils as schema_utils
from bcol_api.services.bcol_payment import BcolPayment
from bcol_api.utils.auth import jwt as _jwt
from bcol_api.utils.constants import Role
from bcol_api.utils.errors import Error
from bcol_api.utils.util import cors_preflight

API = Namespace("bcol accounts", description="Payment System - BCOL Accounts")


@cors_preflight(["POST", "OPTIONS"])
@API.route("", methods=["POST", "OPTIONS"])
class AccountPayment(Resource):
    """Endpoint resource to manage BCOL Payments."""

    @staticmethod
    @_jwt.requires_auth
    @cors.crossdomain(origin="*")
    def post():
        """Create a payment record in BCOL."""
        try:
            is_apply_charge = False
            if _jwt.validate_roles([Role.STAFF.value, Role.EDIT.value]) or _jwt.validate_roles([Role.SYSTEM.value]):
                is_apply_charge = True
            elif _jwt.validate_roles([Role.ACCOUNT_HOLDER.value]):
                is_apply_charge = False
            else:
                abort(403)

            req_json = request.get_json()
            current_app.logger.debug(req_json)
            # Validate the input request
            valid_format = schema_utils.validate(req_json, "payment_request")

            if not valid_format[0]:
                current_app.logger.info(
                    "Validation Error with incoming request %s",
                    schema_utils.serialize(valid_format[1]),
                )
                return error_to_response(
                    Error.INVALID_REQUEST,
                    invalid_params=schema_utils.serialize(valid_format[1]),
                )

            # Override for apply charge, allows for service fees, this is used by CSO's service account.
            if _jwt.validate_roles([Role.SYSTEM.value]) and req_json.get("forceUseDebitAccount") is True:
                is_apply_charge = False

            response, status = (
                BcolPayment().create_payment(req_json, is_apply_charge),
                HTTPStatus.OK,
            )

        except BusinessException as exception:
            return exception.response()
        except PaymentException as exception:
            return exception.response()

        return response, status
