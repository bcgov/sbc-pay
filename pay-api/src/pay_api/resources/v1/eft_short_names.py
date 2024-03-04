# Copyright © 2023 Province of British Columbia
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
"""Resource for EFT Short name."""
from decimal import Decimal
from http import HTTPStatus

from flask import Blueprint, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException
from pay_api.services.eft_short_names import EFTShortnames as EFTShortnameService
from pay_api.services.eft_short_names import EFTShortnamesSearch
from pay_api.services.eft_transactions import EFTTransactions as EFTTransactionService
from pay_api.services.eft_transactions import EFTTransactionSearch
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import Role
from pay_api.utils.util import string_to_date


bp = Blueprint('EFT_SHORT_NAMES', __name__, url_prefix=f'{EndpointEnum.API_V1.value}/eft-shortnames')


@bp.route('', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET'])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def get_eft_shortnames():
    """Get all eft short name records."""
    current_app.logger.info('<get_eft_shortnames')

    state = request.args.get('state', None)
    page: int = int(request.args.get('page', '1'))
    limit: int = int(request.args.get('limit', '10'))
    transaction_start_date = request.args.get('transactionStartDate', None)
    transaction_end_date = request.args.get('transactionEndDate', None)
    deposit_amount = request.args.get('depositAmount', None)
    deposit_start_date = request.args.get('depositStartDate', None)
    deposit_end_date = request.args.get('depositEndDate', None)
    short_name = request.args.get('shortName', None)
    account_id = request.args.get('accountId', None)
    account_id_list = request.args.get('accountIdList', None)
    account_id_list = account_id_list.split(',') if account_id_list else None
    account_name = request.args.get('accountName', None)
    account_branch = request.args.get('accountBranch', None)

    response, status = EFTShortnameService.search(EFTShortnamesSearch(
        account_id=account_id,
        account_id_list=account_id_list,
        account_name=account_name,
        account_branch=account_branch,
        deposit_start_date=string_to_date(deposit_start_date),
        deposit_end_date=string_to_date(deposit_end_date),
        deposit_amount=Decimal(deposit_amount) * Decimal(100) if deposit_amount else None,
        short_name=short_name,
        transaction_start_date=string_to_date(transaction_start_date),
        transaction_end_date=string_to_date(transaction_end_date),
        state=state,
        page=page,
        limit=limit)), HTTPStatus.OK
    current_app.logger.debug('>get_eft_shortnames')
    return jsonify(response), status


@bp.route('/<int:short_name_id>', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET', 'PATCH'])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def get_eft_shortname(short_name_id: int):
    """Get EFT short name details."""
    current_app.logger.info('<get_eft_shortname')

    if not (eft_short_name := EFTShortnameService.find_by_short_name_id(short_name_id)):
        response, status = {'message': 'The requested EFT short name could not be found.'}, \
            HTTPStatus.NOT_FOUND
    else:
        response, status = eft_short_name, HTTPStatus.OK
    current_app.logger.debug('>get_eft_shortname')
    return jsonify(response), status


@bp.route('/<int:short_name_id>', methods=['PATCH'])
@cross_origin(origins='*')
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def patch_eft_shortname(short_name_id: int):
    """Update EFT short name mapping."""
    current_app.logger.info('<patch_eft_shortname')
    request_json = request.get_json()

    try:
        if not EFTShortnameService.find_by_short_name_id(short_name_id):
            response, status = {'message': 'The requested EFT short name could not be found.'}, \
                HTTPStatus.NOT_FOUND
        else:
            account_id = request_json.get('accountId', None)
            response, status = EFTShortnameService.patch(short_name_id, account_id), HTTPStatus.OK
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug('>patch_eft_shortname')
    return jsonify(response), status


@bp.route('/<int:short_name_id>/transactions', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET'])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def get_eft_shortname_transactions(short_name_id: int):
    """Get EFT short name transactions."""
    current_app.logger.info('<get_eft_shortname_transactions')

    page: int = int(request.args.get('page', '1'))
    limit: int = int(request.args.get('limit', '10'))

    response, status = EFTTransactionService.search(short_name_id,
                                                    EFTTransactionSearch(page=page, limit=limit)), HTTPStatus.OK

    current_app.logger.debug('>get_eft_shortname_transactions')
    return jsonify(response), status
