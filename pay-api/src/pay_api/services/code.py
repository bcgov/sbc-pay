# Copyright © 2019 Province of British Columbia
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

from pay_api.models.corp_type import CorpType, CorpTypeSchema
from pay_api.models.error_code import ErrorCode, ErrorCodeSchema
from pay_api.models.fee_code import FeeCode, FeeCodeSchema
from pay_api.models.invoice_status_code import InvoiceStatusCode, InvoiceStatusCodeSchema
from pay_api.models.routing_slip_status_code import RoutingSlipStatusCode, RoutingSlipStatusCodeSchema
from pay_api.utils.cache import cache
from pay_api.utils.enums import Code as CodeValue


class Code:
    """Service to manage Fee related operations."""

    @classmethod
    def build_all_codes_cache(cls):
        """Build cache for all codes."""
        try:
            for code in CodeValue:
                Code.find_code_values_by_type(code.value)
        except SQLAlchemyError as e:
            current_app.logger.info('Error on building cache {}', e)

    @classmethod
    def find_code_values_by_type(
            cls,
            code_type: str
    ):
        """Find code values by code type."""
        current_app.logger.debug(f'<find_code_values_by_type : {code_type}')
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

        response['codes'] = codes_response
        current_app.logger.debug('>find_code_values_by_type')
        return response

    @classmethod
    def find_code_value_by_type_and_code(
            cls,
            code_type: str,
            code: str
    ):
        """Find code values by code type and code."""
        current_app.logger.debug(f'<find_code_value_by_type_and_code : {code_type} - {code}')
        code_response = {}
        if cache.get(code_type):
            filtered_codes = [cd for cd in cache.get(code_type) if cd.get('type') == code or cd.get('code') == code]
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
        current_app.logger.debug('>find_code_value_by_type_and_code')
        return code_response
