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
from pay_api.services.eft_short_names import EFTShortnames as EFTShortnameService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import Role
from pay_api.utils.errors import Error
from pay_api.utils.trace import tracing as _tracing

bp = Blueprint('EFT_SHORT_NAMES', __name__, url_prefix=f'{EndpointEnum.API_V1.value}/eft-shortnames')


@bp.route('', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET'])
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.STAFF.value])
def get_eft_shortnames():
    """Get all eft short name records."""
    current_app.logger.info('<get_eft_shortnames')

    include_all = bool(request.args.get('includeAll', 'false').lower() == 'true')
    page: int = int(request.args.get('page', '1'))
    limit: int = int(request.args.get('limit', '10'))

    response, status = EFTShortnameService.search(include_all, page, limit), HTTPStatus.OK
    current_app.logger.debug('>get_eft_shortnames')
    return jsonify(response), status


@bp.route('/<int:short_name_id>', methods=['GET', 'OPTIONS'])
@cross_origin(origins='*', methods=['GET', 'PATCH'])
@_tracing.trace()
@_jwt.requires_auth
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.STAFF.value])
def get_eft_shortname(short_name_id: int):
    """Get EFT short name details."""
    current_app.logger.info('<get_eft_shortname')

    if not (eft_short_name := EFTShortnameService.find_by_short_name_id(short_name_id)):
        response, status = {'message': 'The requested EFT short name could not be found.'}, \
            HTTPStatus.NOT_FOUND
    else:
        response, status = eft_short_name.asdict(), HTTPStatus.OK
    current_app.logger.debug('>get_eft_shortname')
    return jsonify(response), status


@bp.route('/<int:short_name_id>', methods=['PATCH'])
@cross_origin(origins='*')
@_tracing.trace()
@_jwt.has_one_of_roles([Role.SYSTEM.value, Role.STAFF.value])
def patch_eft_shortname(short_name_id: int):
    """Update EFT short name mapping."""
    current_app.logger.info('<patch_eft_shortname')
    request_json = request.get_json()

    try:
        if not (EFTShortnameService.find_by_short_name_id(short_name_id)):
            response, status = {'message': 'The requested EFT short name could not be found.'}, \
                HTTPStatus.NOT_FOUND
        else:
            account_id = request_json.get('accountId', None)
            response, status = EFTShortnameService.patch(short_name_id, account_id).asdict(), HTTPStatus.OK
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug('>patch_eft_shortname')
    return jsonify(response), status
