# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Service to manage Fee Calculation."""

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import func

from pay_api.models.corp_type import CorpType, CorpTypeSchema
from pay_api.models.error_code import ErrorCode, ErrorCodeSchema
from pay_api.models.fee_code import FeeCode, FeeCodeSchema
from pay_api.models.invoice_status_code import InvoiceStatusCode, InvoiceStatusCodeSchema
from pay_api.models.routing_slip_status_code import RoutingSlipStatusCode, RoutingSlipStatusCodeSchema
from pay_api.utils.cache import cache
from pay_api.utils.enums import Code as CodeValue
from pay_api.utils.enums import PaymentMethod


class Code:
    """Service to manage Fee related operations."""

    @classmethod
    def build_all_codes_cache(cls):
        """Build cache for all codes."""
        try:
            for code in CodeValue:
                Code.find_code_values_by_type(code.value)
        except SQLAlchemyError as e:
            current_app.logger.info("Error on building cache {}", e)

    @classmethod
    def find_code_values_by_type(cls, code_type: str):
        """Find code values by code type."""
        current_app.logger.debug(f"<find_code_values_by_type : {code_type}")
        response = {}

        # Get from cache and if still none look up in database
        codes_response = cache.get(code_type)
        codes_models, schema = None, None
        if not codes_response:
            if code_type == CodeValue.ERROR.value:
                codes_models = ErrorCode.find_all()
                schema = ErrorCodeSchema()
            elif code_type == CodeValue.INVOICE_STATUS.value:
                codes_models = InvoiceStatusCode.find_all()
                schema = InvoiceStatusCodeSchema()
            elif code_type == CodeValue.CORP_TYPE.value:
                codes_models = CorpType.find_all()
                schema = CorpTypeSchema()
            elif code_type == CodeValue.FEE_CODE.value:
                codes_models = FeeCode.find_all()
                schema = FeeCodeSchema()
            elif code_type == CodeValue.ROUTING_SLIP_STATUS.value:
                codes_models = RoutingSlipStatusCode.find_all()
                schema = RoutingSlipStatusCodeSchema()
            if schema and codes_models:
                codes_response = schema.dump(codes_models, many=True)
                cache.set(code_type, codes_response)

        response["codes"] = codes_response
        current_app.logger.debug(">find_code_values_by_type")
        return response

    @classmethod
    def find_code_value_by_type_and_code(cls, code_type: str, code: str):
        """Find code values by code type and code."""
        current_app.logger.debug(f"<find_code_value_by_type_and_code : {code_type} - {code}")
        code_response = {}
        if cache.get(code_type):
            filtered_codes = [cd for cd in cache.get(code_type) if cd.get("type") == code or cd.get("code") == code]
            if filtered_codes:
                code_response = filtered_codes[0]
        else:
            if code_type == CodeValue.ERROR.value:
                codes_model = ErrorCode.find_by_code(code)
                error_schema = ErrorCodeSchema()
                code_response = error_schema.dump(codes_model, many=False)
            elif code_type == CodeValue.INVOICE_STATUS.value:
                codes_model = InvoiceStatusCode.find_by_code(code)
                schema = InvoiceStatusCodeSchema()
                code_response = schema.dump(codes_model, many=False)
            elif code_type == CodeValue.CORP_TYPE.value:
                codes_model = CorpType.find_by_code(code)
                schema = CorpTypeSchema()
                code_response = schema.dump(codes_model, many=False)
        current_app.logger.debug(">find_code_value_by_type_and_code")
        return code_response

    @classmethod
    def find_valid_payment_methods_by_product_code(cls, product_code: str | None = None) -> dict:
        """Find payment methods for a product."""
        if not product_code:
            corp_types = (
                CorpType.query.with_entities(CorpType.product, func.coalesce(CorpType.payment_methods, []))
                .filter(CorpType.product.isnot(None))  # Exclude None at the query level
                .filter(func.cardinality(CorpType.payment_methods) > 0)
                .distinct()
                .all()
            )
            return dict(corp_types)

        corp_type = (
            CorpType.query.with_entities(CorpType.product, CorpType.payment_methods)
            .filter_by(product=product_code)
            .first()
        )
        return {corp_type.product: corp_type.payment_methods or []} if corp_type else {product_code: []}

    @classmethod
    def is_payment_method_valid_for_corp_type(cls, corp_type: str, payment_method: str) -> bool:
        """Check if the given corp_type has the specified payment_method."""
        record = CorpType.query.with_entities(CorpType.payment_methods).filter_by(code=corp_type).first()
        available_payment_methods = record.payment_methods if record else []
        # Online banking can switch to CC payments
        # PAD can pay NSF invoice with CC
        # EFT can pay overdue invoice with CC (potentially)
        if (
            PaymentMethod.ONLINE_BANKING.value in available_payment_methods
            or PaymentMethod.PAD.value in available_payment_methods
            or PaymentMethod.EFT.value in available_payment_methods
        ):
            available_payment_methods.append(PaymentMethod.CC.value)
        return payment_method in available_payment_methods
