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
from typing import Any, Dict

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.utils.errors import Error


class FeeService:
    """Service to manage Fee related operations."""

    @staticmethod
    def calculate_fees(corp_type: str, filing_type_code: str, valid_date: str, jurisdiction: str, priority: bool):
        """Calculate fees for the filing by using the arguments."""
        current_app.logger.debug('<calculate_fees')
        if not corp_type and not filing_type_code:
            raise BusinessException(Error.PAY001)

        fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type(corp_type, filing_type_code, valid_date,
                                                                          jurisdiction, priority)
        if fee_schedule:
            # TODO Query for the service fees and any other processing fees here.. LATER
            fee_response = {
                'filing_type': fee_schedule.filing_type.filing_description,
                'filing_fees': fee_schedule.fee.amount,
                'service_fees': 0,  # TODO Populate Service fees here
                'processing_fees': 0,  # TODO Populate Processing fees here
                'tax':  # TODO Populate Tax details here
                    {
                        'gst': 0,
                        'pst': 0
                    }
            }, 200
        else:
            raise BusinessException(Error.PAY002)

        current_app.logger.debug('>calculate_fees')
        return fee_response
