# Copyright © 2024 Province of British Columbia
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
"""Resource for Payment account."""
from http import HTTPStatus

from flask import Blueprint, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException, ServiceUnavailableException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import CFSService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.errors import Error

bp = Blueprint(
    "BANK_ACCOUNTS",
    __name__,
    url_prefix=f"{EndpointEnum.API_V1.value}/bank-accounts/verifications",
)


@bp.route("", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
@_jwt.requires_auth
def post_bank_account_validate():
    """Validate the bank account details against CFS."""
    current_app.logger.info("<BankAccounts.post")
    request_json = request.get_json()
    # Validate the input request
    valid_format, errors = schema_utils.validate(request_json, "payment_info")

    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))
    try:
        # Remove this later after we migrate to GCP, this cannot be done unless it goes through pay-connector to OCP.
        if current_app.config.get("ENVIRONMENT_NAME") == "sandbox":
            current_app.logger.info("Sandbox environment, returning valid CFS validation mock response.")
            response = {
                "accountNumber": request_json["accountNumber"],
                "bankName": request_json["bankName"],
                "bankNumber": request_json["bankNumber"],
                "branchNumber": request_json["branchNumber"],
                "isValid": True,
                "message": ["VALID"],
                "statusCode": 200,
                "transitAddress": "",
            }
            status = HTTPStatus.OK
        else:
            response, status = CFSService.validate_bank_account(request_json), HTTPStatus.OK

    except BusinessException as exception:
        current_app.logger.error(exception)
        return exception.response()
    except ServiceUnavailableException as exception:
        current_app.logger.error(exception)
        return exception.response()
    current_app.logger.debug(">Account.post")
    return jsonify(response), status
