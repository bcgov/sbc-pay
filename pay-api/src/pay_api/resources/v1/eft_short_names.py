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
from http import HTTPStatus

from flask import Blueprint, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services.eft_service import EftService
from pay_api.services.eft_short_names import EFTShortnames as EFTShortnameService
from pay_api.services.eft_short_name_summaries import EFTShortnameSummaries as EFTShortnameSummariesService
from pay_api.services.eft_short_names import EFTShortnamesSearch
from pay_api.services.eft_transactions import EFTTransactions as EFTTransactionService
from pay_api.services.eft_transactions import EFTTransactionSearch
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import Role
from pay_api.utils.util import string_to_date, string_to_decimal, string_to_int
from pay_api.utils.errors import Error

bp = Blueprint('EFT_SHORT_NAMES', __name__, url_prefix=f'{EndpointEnum.API_V1.value}/eft-shortnames')


@bp.route('', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET'])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def get_eft_shortnames():
    """Get all eft short name records."""
    current_app.logger.info('<get_eft_shortnames')

    state = request.args.get('state').split(',') if request.args.get('state', None) else None
    page: int = int(request.args.get('page', '1'))
    limit: int = int(request.args.get('limit', '10'))
    amount_owing = request.args.get('amountOwing', None)
    short_name = request.args.get('shortName', None)
    short_name_id = request.args.get('shortNameId', None)
    statement_id = request.args.get('statementId', None)
    account_id = request.args.get('accountId', None)
    account_name = request.args.get('accountName', None)
    account_branch = request.args.get('accountBranch', None)

    response, status = EFTShortnameService.search(EFTShortnamesSearch(
        id=short_name_id,
        account_id=account_id,
        account_name=account_name,
        account_branch=account_branch,
        amount_owing=string_to_decimal(amount_owing),
        short_name=short_name,
        statement_id=string_to_int(statement_id),
        state=state,
        page=page,
        limit=limit)), HTTPStatus.OK
    current_app.logger.debug('>get_eft_shortnames')

    return jsonify(response), status


@bp.route('/summaries', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET'])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def get_eft_shortname_summaries():
    """Get all eft short name summaries."""
    current_app.logger.info('<get_eft_shortname_summaries')
    page: int = int(request.args.get('page', '1'))
    limit: int = int(request.args.get('limit', '10'))
    short_name = request.args.get('shortName', None)
    short_name_id = request.args.get('shortNameId', None)
    credits_remaining = request.args.get('creditsRemaining', None)
    linked_accounts_count = request.args.get('linkedAccountsCount', None)
    payment_received_start_date = request.args.get('paymentReceivedStartDate', None)
    payment_received_end_date = request.args.get('paymentReceivedEndDate', None)

    response, status = EFTShortnameSummariesService.search(EFTShortnamesSearch(
        id=string_to_int(short_name_id),
        deposit_start_date=string_to_date(payment_received_start_date),
        deposit_end_date=string_to_date(payment_received_end_date),
        credit_remaining=string_to_decimal(credits_remaining),
        linked_accounts_count=string_to_int(linked_accounts_count),
        short_name=short_name,
        page=page,
        limit=limit)), HTTPStatus.OK

    current_app.logger.debug('>get_eft_shortname_summaries')
    return jsonify(response), status


@bp.route('/<int:short_name_id>', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET'])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def get_eft_shortname(short_name_id: int):
    """Get EFT short name details."""
    current_app.logger.info('<get_eft_shortname')

    if not (eft_short_name := EFTShortnameService.find_by_short_name_id(short_name_id)):
        response, status = {}, HTTPStatus.NOT_FOUND
    else:
        response, status = eft_short_name, HTTPStatus.OK
    current_app.logger.debug('>get_eft_shortname')
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


@bp.route('/<int:short_name_id>/links', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET', 'POST'])
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def get_eft_shortname_links(short_name_id: int):
    """Get EFT short name account links."""
    current_app.logger.info('<get_eft_shortname_links')

    try:
        if not EFTShortnameService.find_by_short_name_id(short_name_id):
            response, status = {}, HTTPStatus.NOT_FOUND
        else:
            response, status = EFTShortnameService.get_shortname_links(short_name_id), HTTPStatus.OK
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug('>get_eft_shortname_links')
    return jsonify(response), status


@bp.route('/<int:short_name_id>/links', methods=['POST'])
@cross_origin(origins='*')
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def post_eft_shortname_link(short_name_id: int):
    """Create EFT short name to account link."""
    current_app.logger.info('<post_eft_shortname_link')
    request_json = request.get_json()

    try:
        if not EFTShortnameService.find_by_short_name_id(short_name_id):
            response, status = {}, HTTPStatus.NOT_FOUND
        else:
            account_id = request_json.get('accountId', None)
            response, status = EFTShortnameService.create_shortname_link(short_name_id, account_id), HTTPStatus.OK
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug('>post_eft_shortname_link')
    return jsonify(response), status


@bp.route('/<int:short_name_id>/links/<int:short_name_link_id>', methods=['DELETE', 'OPTIONS'])
@cross_origin(origins='*', methods=['DELETE'])
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.MANAGE_EFT.value])
def delete_eft_shortname_link(short_name_id: int, short_name_link_id: int):
    """Delete EFT short name to account link."""
    current_app.logger.info('<delete_eft_shortname_link')

    try:
        link = EFTShortnameService.find_link_by_id(short_name_link_id)
        if not link or link['short_name_id'] != short_name_id:
            response, status = {}, HTTPStatus.NOT_FOUND
        else:
            EFTShortnameService.delete_shortname_link(short_name_link_id)
            response, status = None, HTTPStatus.ACCEPTED
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug('>delete_eft_shortname_link')
    return jsonify(response), status


@bp.route('/shortname_refund', methods=['POST', 'OPTIONS'])
@cross_origin(origins='*', methods=['POST'])
@_jwt.has_one_of_roles(
    [Role.SYSTEM.value, Role.MANAGE_EFT.value])
def post_shortname_refund():
    """Create the Refund for the Shortname."""
    current_app.logger.info('<post_shortname_refund')
    request_json = request.get_json(silent=True)
    try:
        valid_format, errors = schema_utils.validate(request_json, 'refund_shortname') if \
            request_json else (True, None)
        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        response = EftService.create_shortname_refund(request_json)
    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug('>post_fas_refund')
    return jsonify(response), HTTPStatus.ACCEPTED
