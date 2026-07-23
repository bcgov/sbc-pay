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
from pay_api.schemas import utils as schema_utils
from pay_api.services import PaymentLinkService, PaymentService
from pay_api.services.auth import check_auth
from pay_api.services.invoice import Invoice as InvoiceService
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.constants import MAKE_PAYMENT
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, Role
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

    token_info = getattr(g, "jwt_oidc_token_info", None) or {}
    roles = (token_info.get("realm_access") or {}).get("roles") or []
    is_external = Role.CREATE_EXTERNAL_INVOICE.value in roles

    try:
        if is_external:
            # Partner client_credentials flow — skip business-level authorization
            # and route the invoice to the SA's adhoc PaymentAccount (keyed by client_id).
            azp = token_info.get("azp") or token_info.get("clientId")
            if not azp:
                return error_to_response(Error.INVALID_REQUEST, invalid_params=[])
            authorization = {
                "account": {
                    "id": f"sa-{azp}",
                    "paymentInfo": {"methodOfPayment": PaymentMethod.DIRECT_PAY.value},
                }
            }
        else:
            business_identifier = get_str_by_path(request_json, "businessInfo/businessIdentifier")
            corp_type_code = get_str_by_path(request_json, "businessInfo/corpType")
            authorization = check_auth(
                business_identifier=business_identifier,
                corp_type_code=corp_type_code,
                contains_role=MAKE_PAYMENT,
            )

        response = PaymentService.create_invoice(request_json, authorization)

        if is_external:
            response = PaymentLinkService.attach_payment_link(response)

        status = HTTPStatus.CREATED
    except (BusinessException, ServiceUnavailableException) as exception:
        return exception.response()
    current_app.logger.debug(">post_invoice")
    return jsonify(response), status


@bp.route("/by-token/<string:token>/link", methods=["POST"])
@cross_origin(origins="*")
@_jwt.requires_auth
def post_link_by_token(token: str):
    """Link an external invoice (identified by its payment link token) to an authenticated user's account.

    Response is a uniform 404 for any token that doesn't currently resolve
    (unknown / already-linked / expired / invalidated) — do not leak which failure
    mode occurred, to avoid enumeration signal.
    """
    current_app.logger.debug("<post_link_by_token")

    try:
        # allow_linked=True so a same-user re-visit with the same URL is idempotent.
        link = PaymentLinkService.resolve_token(token, allow_linked=True)
    except BusinessException:
        return error_to_response(Error.INVALID_REQUEST)

    try:
        invoice = InvoiceService.find_by_id(link.invoice_id, skip_auth_check=True)

        target_account_id = request.headers.get("Account-Id")
        if not target_account_id:
            current_app.logger.info("post_link_by_token: missing Account-Id header")
            return error_to_response(Error.INVALID_REQUEST)

        current_app.logger.info(
            "post_link_by_token: calling check_auth for account_id=%s (invoice=%s, linked_at=%s)",
            target_account_id,
            link.invoice_id,
            link.linked_at,
        )
        # 403 if the user has no MAKE_PAYMENT authority on the target account.
        authorization = check_auth(
            business_identifier=None,
            account_id=target_account_id,
            contains_role=MAKE_PAYMENT,
        )

        target_account = PaymentAccountService.find_account(authorization)
        if not target_account:
            payment_method = (
                get_str_by_path(authorization, "account/paymentInfo/methodOfPayment")
                or PaymentMethod.DIRECT_PAY.value
            )
            target_account = PaymentAccountService.create(
                {
                    "accountId": target_account_id,
                    "paymentInfo": {"methodOfPayment": payment_method},
                }
            )

        if link.linked_at is not None:
            # Idempotent re-visit: the invoice is already linked. Only allow the
            # user to proceed if they're the same account the link was bound to.
            # Different account = we do not re-bind — the original owner keeps it.
            if invoice._dao.payment_account_id != target_account.id:  # pylint: disable=protected-access
                current_app.logger.info(
                    "post_link_by_token: token linked to account %s but caller has %s",
                    invoice._dao.payment_account_id,  # pylint: disable=protected-access
                    target_account.id,
                )
                return error_to_response(Error.INVALID_REQUEST)
            # No mutation — just return the current invoice DTO. The client uses
            # invoice_status_code (PAID/CREATED/APPROVED/etc.) to decide what to render.
        else:
            # First-time link: invoice must still be in a linkable state.
            if invoice.invoice_status_code not in (InvoiceStatus.CREATED.value, InvoiceStatus.APPROVED.value):
                current_app.logger.info(
                    "post_link_by_token: invoice %s not linkable (status=%s)",
                    link.invoice_id,
                    invoice.invoice_status_code,
                )
                return error_to_response(Error.INVALID_REQUEST)

            invoice._dao.payment_account_id = target_account.id  # pylint: disable=protected-access
            invoice._dao.cfs_account_id = target_account.cfs_account_id  # pylint: disable=protected-access
            invoice.save()
            PaymentLinkService.mark_linked(link)

        response = InvoiceService.find_by_id(link.invoice_id, skip_auth_check=True).asdict(include_dynamic_fields=True)
        status = HTTPStatus.OK
    except ServiceUnavailableException as exception:
        current_app.logger.exception("post_link_by_token: downstream 503 (auth-api / CFS / etc.)")
        return exception.response()
    except BusinessException as exception:
        return exception.response()

    current_app.logger.debug(">post_link_by_token")
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
