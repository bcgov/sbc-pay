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
"""Resource for code endpoints."""

from http import HTTPStatus

from flask import Blueprint
from flask_cors import cross_origin

from pay_api.services.code import Code as CodeService
from pay_api.utils.endpoints_enums import EndpointEnum

bp = Blueprint("CODES", __name__, url_prefix=f"{EndpointEnum.API_V1.value}/codes")


@bp.route("/<string:code_type>", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
def get_codes_by_type(code_type):
    """Return all codes based on code_type."""
    return CodeService.find_code_values_by_type(code_type), HTTPStatus.OK


@bp.route("/<string:code_type>/<string:code>", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
def get_code(code_type, code):
    """Return all codes based on code_type."""
    return CodeService.find_code_value_by_type_and_code(code_type, code), HTTPStatus.OK


@bp.route("/valid_payment_methods", methods=["GET", "OPTIONS"])
@bp.route("/valid_payment_methods/<string:product_code>", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
def get_valid_payment_methods(product_code=None):
    """Return all valid payment methods based on product code."""
    return CodeService.find_valid_payment_methods_by_product_code(product_code), HTTPStatus.OK
