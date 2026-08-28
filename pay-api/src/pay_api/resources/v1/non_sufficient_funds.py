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
"""Resource for Account Non-Sufficient Funds endpoints."""

from http import HTTPStatus

from flask import Blueprint, Response, current_app, jsonify
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException
from pay_api.services import NonSufficientFundsService
from pay_api.services.auth import check_auth
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import EDIT_ROLE, MAKE_PAYMENT, VIEW_ROLE
from pay_api.utils.endpoints_enums import EndpointEnum

bp = Blueprint(
    "NON_SUFFICIENT_FUNDS",
    __name__,
    url_prefix=f"{EndpointEnum.API_V1.value}/accounts/<string:account_id>/nsf",
)


@bp.route("", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET"])
@_jwt.requires_auth
def get_non_sufficient_funds(account_id: str):
    """Get non sufficient funds."""
    current_app.logger.info("<get_non_sufficient_funds")
    # Check if user is authorized to perform this action
    check_auth(
        business_identifier=None,
        account_id=account_id,
        one_of_roles=[MAKE_PAYMENT, EDIT_ROLE, VIEW_ROLE],
    )
    response, status = (
        NonSufficientFundsService.find_all_non_sufficient_funds_invoices(account_id=account_id),
        HTTPStatus.OK,
    )
    current_app.logger.debug(">get_non_sufficient_funds")
    return jsonify(response), status


@bp.route("/statement", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
@_jwt.requires_auth
def get_non_sufficient_funds_statement_pdf(account_id: str):
    """Get non sufficient funds statement pdf."""
    current_app.logger.info("<get_non_sufficient_funds_statement_pdf")
    # Check if user is authorized to perform this action
    check_auth(
        business_identifier=None,
        account_id=account_id,
        one_of_roles=[MAKE_PAYMENT, EDIT_ROLE, VIEW_ROLE],
    )
    try:
        pdf, pdf_filename = NonSufficientFundsService.create_non_sufficient_funds_statement_pdf(account_id=account_id)
        response = Response(pdf, 201)
        response.headers.set("Content-Disposition", "attachment", filename=f"{pdf_filename}.pdf")
        response.headers.set("Content-Type", "application/pdf")
        response.headers.set("Access-Control-Expose-Headers", "Content-Disposition")
        current_app.logger.debug(">get_non_sufficient_funds_statement")
        return response
    except BusinessException as exception:
        current_app.logger.debug(">get_non_sufficient_funds_statement_pdf")
        return exception.response()
