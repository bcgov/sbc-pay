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

from pay_api.exceptions import BusinessException
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.utils.errors import Error
from sbc_common_components.tracing.service_tracing import ServiceTracing


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
        return self._fee_amount + self.pst + self.gst

    @property
    def fee_amount(self):
        """Return the fee amount."""
        return self._fee_amount

    @property
    def service_fees(self):
        """Return the fee amount."""
        return 0  # TODO

    @property
    def gst(self):
        """Return the fee amount."""
        return 0  # TODO

    @property
    def pst(self):
        """Return the fee amount."""
        return 0  # TODO

    @property
    def processing_fees(self):
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
            'service_fees': self.service_fees,
            'processing_fees': self.processing_fees,
            'tax': {
                'gst': self.gst,
                'pst': self.pst
            },
            'total': self.total
        }
        # if self.description:
        #   d['description'] = self.description
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
            jurisdiction: str,
            priority: bool,
    ):
        """Calculate fees for the filing by using the arguments."""
        current_app.logger.debug('<get_fees_by_corp_type_and_filing_type')
        if not corp_type and not filing_type_code:
            raise BusinessException(Error.PAY001)
        if jurisdiction or priority:
            current_app.logger.warn('Not using Jurisdiction and priority now!!!')
        fee_schedule_dao = FeeScheduleModel.find_by_filing_type_and_corp_type(corp_type, filing_type_code, valid_date)

        if not fee_schedule_dao:
            raise BusinessException(Error.PAY002)
        fee_schedule = FeeSchedule()
        fee_schedule._dao = fee_schedule_dao  # pylint: disable=protected-access

        current_app.logger.debug('>get_fees_by_corp_type_and_filing_type')
        return fee_schedule
