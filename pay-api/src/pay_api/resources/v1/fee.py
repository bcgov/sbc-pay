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
"""Resource for Fee Calculation endpoints."""
from datetime import datetime, timezone
from http import HTTPStatus

from flask import Blueprint, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.dtos.product import ProductFeeGetRequest
from pay_api.exceptions import BusinessException
from pay_api.services import FeeSchedule
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import DEFAULT_JURISDICTION, DT_SHORT_FORMAT
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import Role
from pay_api.utils.util import convert_to_bool

bp = Blueprint("FEES", __name__, url_prefix=f"{EndpointEnum.API_V1.value}/fees")


@bp.route("/<string:corp_type>/<string:filing_type_code>", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
@_jwt.has_one_of_roles([Role.VIEWER.value, Role.EDITOR.value, Role.STAFF.value])
def get_fee_by_corp_and_filing_type(corp_type, filing_type_code):
    """Calculate the fee for the filing using the corp type/filing type and return fee."""
    date = request.args.get("date", datetime.now(tz=timezone.utc).strftime(DT_SHORT_FORMAT))
    is_priority = convert_to_bool(request.args.get("priority", "False"))
    is_future_effective = convert_to_bool(request.args.get("futureEffective", "False"))
    jurisdiction = request.args.get("jurisdiction", DEFAULT_JURISDICTION)
    quantity = int(request.args.get("quantity", 1))
    waive_fees = False
    if _jwt.validate_roles([Role.STAFF.value]):
        waive_fees = convert_to_bool(request.args.get("waiveFees", "False"))

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
            ).asdict(),
            HTTPStatus.OK,
        )
    except BusinessException as exception:
        return exception.response()
    return jsonify(response), status


@bp.route("", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
def get_products_fees():
    """Get Products Fees - the cost of a filing and the list of filings."""
    request_data = ProductFeeGetRequest.from_dict(request.args.to_dict())
    current_app.logger.debug("request_data.product_code: %s", request_data.product_code)
    try:
        response, status = (FeeSchedule.get_fee_details(request_data.product_code), HTTPStatus.OK)
    except BusinessException as exception:
        return exception.response()
    return jsonify(response), status
