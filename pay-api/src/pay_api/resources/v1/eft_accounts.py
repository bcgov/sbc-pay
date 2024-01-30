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
"""Resource for Payment account."""
from http import HTTPStatus

from flask import Blueprint, current_app, request
from flask_cors import cross_origin

from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import Role
from pay_api.utils.trace import tracing as _tracing

bp = Blueprint('EFT_ACCOUNTS', __name__, url_prefix=f'{EndpointEnum.API_V1.value}/eft-accounts')


@bp.route('', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET'])
@_tracing.trace()
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.STAFF.value])
def get_eft_accounts():
    """Get EFT Payment Accounts."""
    page: int = int(request.args.get('page', '1'))
    limit: int = int(request.args.get('limit', '10'))

    current_app.logger.info('<get_eft_accounts')

    response, status = PaymentAccountService.find_eft_accounts(page, limit), HTTPStatus.OK

    current_app.logger.debug('>get_eft_accounts')
    return response, status
