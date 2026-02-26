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
"""Resource for routing slip v2 endpoints."""

from http import HTTPStatus

from flask import Blueprint, current_app, jsonify
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException
from pay_api.services.fas import RoutingSlipService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import Role

bp = Blueprint(
    "FAS_ROUTING_SLIPS_V2",
    __name__,
    url_prefix=f"{EndpointEnum.API_V2.value}/fas/routing-slips",
)


@bp.route("/<string:routing_slip_number>", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
@_jwt.has_one_of_roles([Role.FAS_VIEW.value])
def get_routing_slip(routing_slip_number: str):
    """Get routing slip."""
    current_app.logger.info("<get_routing_slip_v2")
    try:
        response = RoutingSlipService.validate_and_find_by_number(routing_slip_number, 2)
        if response:
            status = HTTPStatus.OK
        else:
            response, status = {}, HTTPStatus.NO_CONTENT
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug(">get_routing_slip_v2")
    return jsonify(response), status
