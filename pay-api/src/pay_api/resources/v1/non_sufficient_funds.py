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
"""Resource for Account Non-Sufficient Funds endpoints."""
from http import HTTPStatus

from flask import Blueprint, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.services import NonSufficientFundsService
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import EDIT_ROLE, MAKE_PAYMENT, VIEW_ROLE
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.trace import tracing as _tracing


bp = Blueprint('NON_SUFFICIENT_FUNDS', __name__,
               url_prefix=f'{EndpointEnum.API_V1.value}/accounts/<string:account_id>/nsf')


@bp.route('', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET', 'POST'])
@_tracing.trace()
@_jwt.requires_auth
def get_non_sufficient_funds(account_id: str):
    """Get non sufficient funds."""
    current_app.logger.info('<get_non_sufficient_funds')
    # Check if user is authorized to perform this action
    check_auth(business_identifier=None, account_id=account_id, one_of_roles=[MAKE_PAYMENT, EDIT_ROLE, VIEW_ROLE])
    page: int = int(request.args.get('page', '1'))
    limit: int = int(request.args.get('limit', '10'))
    response, status = NonSufficientFundsService.find_all_non_sufficient_funds_invoices(account_id=account_id,
                                                                                        page=page, 
                                                                                        limit=limit), HTTPStatus.OK
    current_app.logger.debug('>get_non_sufficient_funds')
    return jsonify(response), status
