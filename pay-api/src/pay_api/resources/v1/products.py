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
"""Resource for products(pay related) endpoints."""
from http import HTTPStatus

from flask import Blueprint
from flask_cors import cross_origin

from pay_api.services import PaymentMethodService
from pay_api.utils.endpoints_enums import EndpointEnum

bp = Blueprint("PRODUCTS", __name__, url_prefix=f"{EndpointEnum.API_V1.value}/products")


@bp.route("/valid_payment_methods/<product_code>", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
def get_products(product_code):
    """Return all valid payment methods based on product code."""
    return PaymentMethodService.find_payment_methods(product_code), HTTPStatus.OK
