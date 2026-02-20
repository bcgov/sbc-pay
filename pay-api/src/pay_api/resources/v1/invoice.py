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
"""Resource for Payment Request/Invoice endpoints."""

from http import HTTPStatus

from flask import Blueprint, Response, current_app, g, jsonify, request
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException, ServiceUnavailableException, error_to_response
from pay_api.models import Invoice as InvoiceModel
from pay_api.schemas import utils as schema_utils
from pay_api.services import PaymentService
from pay_api.services.auth import check_auth
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.invoice import Invoice as InvoiceService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import MAKE_PAYMENT
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import Role, TransactionStatus
from pay_api.utils.errors import Error
from pay_api.utils.util import get_str_by_path

bp = Blueprint("INVOICE", __name__, url_prefix=f"{EndpointEnum.API_V1.value}/payment-requests")


@bp.route("", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "POST"])
@_jwt.requires_roles([Role.SYSTEM.value])
def get_invoices():
    """Get the invoice records."""
    current_app.logger.info("<get_invoices")
    business_identifier = request.args.get("businessIdentifier", None)
    try:
        response, status = (
            InvoiceService.find_invoices(business_identifier=business_identifier),
            HTTPStatus.OK,
        )
    except (BusinessException, ServiceUnavailableException) as exception:
        return exception.response()
    current_app.logger.debug(">get_invoices")
    return jsonify(response), status


@bp.route("", methods=["POST"])
@cross_origin(origins="*")
@_jwt.requires_auth
def post_invoice():
    """Create the payment request records."""
    request_json = request.get_json()
    current_app.logger.debug(f"<Payment Request : {request_json}")
    valid_format, errors = schema_utils.validate(request_json, "payment_request")

    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

    # Check if user is authorized to perform this action
    business_identifier = get_str_by_path(request_json, "businessInfo/businessIdentifier")
    corp_type_code = get_str_by_path(request_json, "businessInfo/corpType")
    authorization = check_auth(
        business_identifier=business_identifier,
        corp_type_code=corp_type_code,
        contains_role=MAKE_PAYMENT,
    )
    try:
        response, status = (
            PaymentService.create_invoice(request_json, authorization),
            HTTPStatus.CREATED,
        )
    except (BusinessException, ServiceUnavailableException) as exception:
        return exception.response()
    current_app.logger.debug(">post_invoice")
    return jsonify(response), status


@bp.route("/<int:invoice_id>", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "DELETE", "PATCH"])
@_jwt.requires_auth
def get_invoice(invoice_id):
    """Get the invoice records."""
    try:
        response, status = (
            InvoiceService.find_by_id(invoice_id).asdict(include_dynamic_fields=True),
            HTTPStatus.OK,
        )
    except BusinessException as exception:
        return exception.response()
    return jsonify(response), status


@bp.route("/<int:invoice_id>", methods=["DELETE"])
@cross_origin(origins="*")
@_jwt.requires_auth
def delete_invoice(invoice_id):
    """Soft delete the invoice records."""
    current_app.logger.info("<delete_invoice")

    try:
        PaymentService.accept_delete(invoice_id)

        response, status = None, HTTPStatus.ACCEPTED

    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug(">delete_invoice")
    return jsonify(response), status


@bp.route("/<int:invoice_id>", methods=["PATCH"])
@cross_origin(origins="*")
@_jwt.requires_auth
def patch_invoice(invoice_id: int = None):
    """Update the payment method for an online banking ."""
    current_app.logger.info("<Invoices.patch for invoice : %s", invoice_id)

    request_json = request.get_json()
    current_app.logger.debug(request_json)
    # Validate the input request
    valid_format, errors = schema_utils.validate(request_json, "payment_info")

    is_apply_credit = request.args.get("applyCredit", "false").lower() == "true"

    if not valid_format:
        return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

    try:
        response, status = (
            PaymentService.update_invoice(invoice_id, request_json, is_apply_credit),
            HTTPStatus.OK,
        )
    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">patch_invoice")
    return jsonify(response), status


@bp.route("/<int:invoice_id>/composite", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "DELETE", "PATCH"])
@_jwt.requires_auth
def get_invoice_composite(invoice_id):
    """Get the invoice records."""
    try:
        response, status = (
            InvoiceService.find_composite_by_id(invoice_id),
            HTTPStatus.OK,
        )
    except BusinessException as exception:
        return exception.response()
    return jsonify(response), status


@bp.route("/<int:invoice_id>/reports", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
@_jwt.requires_auth
def post_invoice_report(invoice_id: int = None):
    """Update the payment method for an online banking ."""
    current_app.logger.info("<InvoiceReport.post for invoice : %s", invoice_id)

    try:
        pdf, file_name = InvoiceService.create_invoice_pdf(invoice_id)
        response = Response(pdf, 201)
        response.headers.set("Content-Disposition", "attachment", filename=f"{file_name}.pdf")
        response.headers.set("Content-Type", "application/pdf")
        response.headers.set("Access-Control-Expose-Headers", "Content-Disposition")
        return response

    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">post_invoice_report")
    return jsonify(response), 200


@bp.route("/<int:invoice_id>/release", methods=["POST", "OPTIONS"])
@cross_origin(origins="*", methods=["POST"])
@_jwt.requires_roles([Role.SYSTEM.value])
def post_invoice_release(invoice_id):
    """Release a payment record for the invoice."""
    current_app.logger.info("<post_invoice_release for invoice : %s", invoice_id)
    token_info = g.jwt_oidc_token_info or {}
    if token_info.get("azp") != "sbc-pay":
        return error_to_response(Error.INVALID_CLIENT)

    invoice = InvoiceModel.find_by_id(invoice_id)
    if not invoice:
        raise BusinessException(Error.INVALID_INVOICE_ID)

    PaymentSystemService.release_payment_or_reversal(
        invoice,
        transaction_status=TransactionStatus.COMPLETED.value,
    )
    current_app.logger.debug(">post_invoice_release")
    return jsonify(None), HTTPStatus.OK
