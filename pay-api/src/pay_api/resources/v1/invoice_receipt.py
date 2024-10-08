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
"""Resource for Transaction endpoints."""

from flask import Blueprint, Response, current_app, jsonify, request
from flask_cors import cross_origin

from pay_api.exceptions import BusinessException, error_to_response
from pay_api.schemas import utils as schema_utils
from pay_api.services import ReceiptService
from pay_api.utils.auth import jwt as _jwt
from pay_api.utils.endpoints_enums import EndpointEnum
from pay_api.utils.errors import Error


bp = Blueprint(
    "INVOICE_RECEIPTS",
    __name__,
    url_prefix=f"{EndpointEnum.API_V1.value}/payment-requests/<int:invoice_id>",
)


@bp.route("/receipts", methods=["GET", "OPTIONS"])
@cross_origin(origins="*", methods=["GET", "POST"])
@_jwt.requires_auth
def get_invoice_receipt(invoice_id):
    """Return the receipt details."""
    current_app.logger.info("<get_invoice_receipt")
    try:
        receipt_details = ReceiptService.get_receipt_details({}, invoice_id, skip_auth_check=False)
        receipt_details.pop("paymentMethodDescription", None)

    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">get_invoice_receipt")
    return jsonify(receipt_details), 200


@bp.route("/receipts", methods=["POST"])
@cross_origin(origins="*")
@_jwt.requires_auth
def post_invoice_receipt(invoice_id):
    """Create the Receipt for the Invoice."""
    request_json = request.get_json()
    current_app.logger.info("<post_invoice_receipt")
    try:
        valid_format, errors = schema_utils.validate(request_json, "payment_receipt_input")
        if not valid_format:
            return error_to_response(Error.INVALID_REQUEST, invalid_params=schema_utils.serialize(errors))

        pdf = ReceiptService.create_receipt(invoice_id, request_json)
        current_app.logger.info("<InvoiceReceipt received pdf")
        response = Response(pdf, 201)
        file_name = request_json.get("fileName")
        file_name = "Coops-Filing" if not file_name else file_name
        response.headers.set("Content-Disposition", "attachment", filename=f"{file_name}.pdf")
        response.headers.set("Content-Type", "application/pdf")
        response.headers.set("Access-Control-Expose-Headers", "Content-Disposition")
        return response

    except BusinessException as exception:
        return exception.response()
    current_app.logger.debug(">post_invoice_receipt")
    return jsonify(response), 200
