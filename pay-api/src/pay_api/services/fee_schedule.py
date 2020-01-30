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

from datetime import date

from flask import current_app
from sbc_common_components.tracing.service_tracing import ServiceTracing

from pay_api.exceptions import BusinessException
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.utils.errors import Error


@ServiceTracing.trace(ServiceTracing.enable_tracing, ServiceTracing.should_be_tracing)
class FeeSchedule:  # pylint: disable=too-many-instance-attributes
    """Service to manage Fee related operations."""

    def __init__(self):
        """Return a User Service object."""
        self.__dao = None
        self._fee_schedule_id: int = None
        self._filing_type_code: str = None
        self._corp_type_code: str = None
        self._fee_code: str = None
        self._fee_start_date: date = None
        self._fee_end_date: date = None
        self._fee_amount: float = None
        self._filing_type: str = None
        self._priority_fee: float = 0
        self._future_effective_fee: float = 0
        self._waived_fee_amount: float = 0

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = FeeScheduleModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.fee_schedule_id: int = self._dao.fee_schedule_id
        self.filing_type_code: str = self._dao.filing_type_code
        self.corp_type_code: str = self._dao.corp_type_code
        self.fee_code: str = self._dao.fee_code
        self.fee_start_date: date = self._dao.fee_start_date
        self.fee_end_date: date = self._dao.fee_end_date
        self._fee_amount: float = self._dao.fee.amount
        self._filing_type: str = self._dao.filing_type.description

    @property
    def fee_schedule_id(self):
        """Return the fee_schedule_id."""
        return self._fee_schedule_id

    @fee_schedule_id.setter
    def fee_schedule_id(self, value: int):
        """Set the fee_schedule_id."""
        self._fee_schedule_id = value
        self._dao.fee_schedule_id = value

    @property
    def filing_type_code(self):
        """Return the filing_type_code."""
        return self._filing_type_code

    @filing_type_code.setter
    def filing_type_code(self, value: str):
        """Set the filing_type_code."""
        self._filing_type_code = value
        self._dao.filing_type_code = value

    @property
    def corp_type_code(self):
        """Return the corp_type_code."""
        return self._corp_type_code

    @corp_type_code.setter
    def corp_type_code(self, value: str):
        """Set the corp_type_code."""
        self._corp_type_code = value
        self._dao.corp_type_code = value

    @property
    def fee_code(self):
        """Return the fee_code."""
        return self._fee_code

    @fee_code.setter
    def fee_code(self, value: str):
        """Set the fee_code."""
        self._fee_code = value
        self._dao.fee_code = value

    @property
    def fee_start_date(self):
        """Return the fee_start_date."""
        return self._fee_start_date

    @fee_start_date.setter
    def fee_start_date(self, value: date):
        """Set the fee_start_date."""
        self._fee_start_date = value
        self._dao.fee_start_date = value

    @property
    def fee_end_date(self):
        """Return the fee_end_date."""
        return self._fee_end_date

    @fee_end_date.setter
    def fee_end_date(self, value: str):
        """Set the fee_end_date."""
        self._fee_end_date = value
        self._dao.fee_end_date = value

    @property
    def description(self):
        """Return the description."""
        return self._filing_type

    @property
    def total(self):
        """Return the total fees calculated."""
        return self._fee_amount + self.pst + self.gst + self.priority_fee + self.future_effective_fee

    @property
    def fee_amount(self):
        """Return the fee amount."""
        return self._fee_amount

    @fee_amount.setter
    def fee_amount(self, fee_amount):
        """Override the fee amount."""
        # set waived fees attribute to original fee amount
        self._waived_fee_amount = self._fee_amount
        # Override the fee amount
        self._fee_amount = fee_amount

    @property
    def waived_fee_amount(self):
        """Return waived fee amount."""
        return self._waived_fee_amount

    @property
    def priority_fee(self):
        """Return the priority fee."""
        return self._priority_fee

    @priority_fee.setter
    def priority_fee(self, value: float):
        """Set the priority fee."""
        self._priority_fee = value

    @property
    def future_effective_fee(self):
        """Return the future_effective_fee."""
        return self._future_effective_fee

    @future_effective_fee.setter
    def future_effective_fee(self, value: float):
        """Set the future_effective_fee."""
        self._future_effective_fee = value

    @property
    def gst(self):
        """Return the fee amount."""
        return 0  # TODO

    @property
    def pst(self):
        """Return the fee amount."""
        return 0  # TODO

    @property
    def quantity(self):
        """Return the fee amount."""
        return 1  # TODO

    @description.setter
    def description(self, value: str):
        """Set the description."""
        self._filing_type = value

    @ServiceTracing.disable_tracing
    def asdict(self):
        """Return the User as a python dict."""
        d = {
            'filing_type': self._filing_type,
            'filing_type_code': self.filing_type_code,
            'filing_fees': self.fee_amount,
            'priority_fees': self.priority_fee,
            'future_effective_fees': self.future_effective_fee,
            'tax': {
                'gst': self.gst,
                'pst': self.pst
            },
            'total': self.total,
            'service_fees': 0,  # TODO Remove
            'processing_fees': 0  # TODO Remove
        }
        return d

    def save(self):
        """Save the fee schedule information."""
        self._dao.save()

    @classmethod
    def find_by_corp_type_and_filing_type(  # pylint: disable=too-many-arguments
            cls,
            corp_type: str,
            filing_type_code: str,
            valid_date: date,
            **kwargs
    ):
        """Calculate fees for the filing by using the arguments."""
        current_app.logger.debug('<get_fees_by_corp_type_and_filing_type')
        if not corp_type and not filing_type_code:
            raise BusinessException(Error.PAY001)
        if kwargs.get('jurisdiction'):
            current_app.logger.warn('Not using Jurisdiction now!!!')

        fee_schedule_dao = FeeScheduleModel.find_by_filing_type_and_corp_type(corp_type, filing_type_code, valid_date)

        if not fee_schedule_dao:
            raise BusinessException(Error.PAY002)
        fee_schedule = FeeSchedule()
        fee_schedule._dao = fee_schedule_dao  # pylint: disable=protected-access

        if kwargs.get('is_priority') and fee_schedule_dao.priority_fee:
            fee_schedule.priority_fee = fee_schedule_dao.priority_fee.amount
        if kwargs.get('is_future_effective') and fee_schedule_dao.future_effective_fee:
            fee_schedule.future_effective_fee = fee_schedule_dao.future_effective_fee.amount
        if kwargs.get('waive_fees'):
            fee_schedule.fee_amount = 0

        current_app.logger.debug('>get_fees_by_corp_type_and_filing_type')
        return fee_schedule
