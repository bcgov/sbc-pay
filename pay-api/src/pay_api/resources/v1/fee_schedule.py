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
from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException
from pay_api.services import FeeSchedule
from pay_api.utils.endpoints_enums import EndpointEnum

bp = Blueprint("FEE_SCHEDULE", __name__, url_prefix=f"{EndpointEnum.API_V1.value}/fees/schedules")


@bp.route("", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
def get_fee_schedules():
    """Calculate the fee for the filing using the corp type/filing type and return fee."""
    try:
        corp_type = request.args.get("corp_type", None)
        filing_type = request.args.get("filing_type", None)
        description = request.args.get("description", None)
        response, status = (
            FeeSchedule.find_all(
                corp_type_code=corp_type,
                filing_type_code=filing_type,
                description=description,
            ),
            HTTPStatus.OK,
        )
    except BusinessException as exception:
        return exception.response()
    return jsonify(response), status
