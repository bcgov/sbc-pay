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

from datetime import date
from decimal import Decimal

from flask import current_app
from sbc_common_components.tracing.service_tracing import ServiceTracing

from pay_api.exceptions import BusinessException
from pay_api.models import AccountFee as AccountFeeModel
from pay_api.models import FeeCode as FeeCodeModel
from pay_api.models import FeeDetailsSchema
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import FeeScheduleSchema
from pay_api.utils.enums import Role
from pay_api.utils.errors import Error
from pay_api.utils.user_context import UserContext, user_context


@ServiceTracing.trace(ServiceTracing.enable_tracing, ServiceTracing.should_be_tracing)
class FeeSchedule:  # pylint: disable=too-many-public-methods, too-many-instance-attributes
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
        self._fee_amount = Decimal("0")
        self._filing_type: str = None
        self._priority_fee = Decimal("0")
        self._future_effective_fee = Decimal("0")
        self._waived_fee_amount = Decimal("0")
        self._quantity: int = 1
        self._service_fees = Decimal("0")
        self._service_fee_code: str = None
        self._variable: bool = False

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
        self._fee_amount: Decimal = self._dao.fee.amount
        self._filing_type: str = self._dao.filing_type.description
        self._service_fee_code: str = self._dao.service_fee_code
        self._variable: bool = self._dao.variable

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
        return (
            self._fee_amount + self.pst + self.gst + self.priority_fee + self.future_effective_fee + self.service_fees
        )

    @property
    def total_excluding_service_fees(self):
        """Return the total excluding service fees fees calculated."""
        return self._fee_amount + self.pst + self.gst + self.priority_fee + self.future_effective_fee

    @property
    def fee_amount(self):
        """Return the fee amount."""
        return self._fee_amount

    @fee_amount.setter
    def fee_amount(self, fee_amount):
        """Override the fee amount."""
        # set waived fees attribute to original fee amount
        if fee_amount == 0 and not self._variable:
            self._waived_fee_amount = self._fee_amount + self._priority_fee + self._future_effective_fee
        # Override the fee amount
        self._fee_amount = fee_amount

    @property
    def waived_fee_amount(self):
        """Return waived fee amount."""
        return self._waived_fee_amount

    @waived_fee_amount.setter
    def waived_fee_amount(self, waived_fee_amount):
        """Set waived fee amount."""
        self._waived_fee_amount = waived_fee_amount

    @property
    def priority_fee(self):
        """Return the priority fee."""
        return self._priority_fee

    @priority_fee.setter
    def priority_fee(self, value: Decimal):
        """Set the priority fee."""
        self._priority_fee = value

    @property
    def future_effective_fee(self):
        """Return the future_effective_fee."""
        return self._future_effective_fee

    @future_effective_fee.setter
    def future_effective_fee(self, value: Decimal):
        """Set the future_effective_fee."""
        self._future_effective_fee = value

    @property
    def service_fees(self):
        """Return the service_fees."""
        return self._service_fees

    @service_fees.setter
    def service_fees(self, value: Decimal):
        """Set the service_fees."""
        self._service_fees = value

    @property
    def gst(self):
        """Return the fee amount."""
        return 0

    @property
    def pst(self):
        """Return the fee amount."""
        return 0

    @property
    def quantity(self):
        """Return the quantity."""
        return self._quantity

    @quantity.setter
    def quantity(self, value: int):
        """Set the quantity."""
        self._quantity = value
        if self._quantity and self._quantity > 1:
            self._fee_amount = self._fee_amount * self._quantity

    @description.setter
    def description(self, value: str):
        """Set the description."""
        self._filing_type = value

    @property
    def service_fee_code(self):
        """Return the service_fee_code."""
        return self._service_fee_code

    @service_fee_code.setter
    def service_fee_code(self, value: int):
        """Set the service_fee_code."""
        self._service_fee_code = value
        self._dao.service_fee_code = value

    @property
    def variable(self) -> bool:
        """Return the service_fee_code."""
        return self._variable

    @ServiceTracing.disable_tracing
    def asdict(self):
        """Return the User as a python dict."""
        d = {
            "filing_type": self._filing_type,
            "filing_type_code": self.filing_type_code,
            "filing_fees": float(self.fee_amount),
            "priority_fees": float(self.priority_fee),
            "future_effective_fees": float(self.future_effective_fee),
            "tax": {"gst": float(self.gst), "pst": float(self.pst)},
            "total": float(self.total),
            "service_fees": float(self._service_fees),
            "processing_fees": 0,
        }
        return d

    def save(self):
        """Save the fee schedule information."""
        self._dao.save()

    @classmethod
    @user_context
    def find_by_corp_type_and_filing_type(  # pylint: disable=too-many-arguments
        cls, corp_type: str, filing_type_code: str, valid_date: date, **kwargs
    ):
        """Calculate fees for the filing by using the arguments."""
        current_app.logger.debug(
            f"<get_fees_by_corp_type_and_filing_type : {corp_type}, {filing_type_code}, " f"{valid_date}"
        )
        user: UserContext = kwargs["user"]

        if not corp_type and not filing_type_code:
            raise BusinessException(Error.INVALID_CORP_OR_FILING_TYPE)

        fee_schedule_dao = FeeScheduleModel.find_by_filing_type_and_corp_type(corp_type, filing_type_code, valid_date)

        if not fee_schedule_dao:
            raise BusinessException(Error.INVALID_CORP_OR_FILING_TYPE)

        fee_schedule = FeeSchedule()
        fee_schedule._dao = fee_schedule_dao  # pylint: disable=protected-access
        fee_schedule.quantity = kwargs.get("quantity")

        # Find fee overrides for account.
        account_fee = AccountFeeModel.find_by_auth_account_id_and_corp_type(user.account_id, corp_type)

        apply_filing_fees: bool = account_fee.apply_filing_fees if account_fee else True
        if not apply_filing_fees:
            fee_schedule.fee_amount = 0
            fee_schedule.waived_fee_amount = 0

        # Set transaction fees
        fee_schedule.service_fees = FeeSchedule.calculate_service_fees(fee_schedule_dao, account_fee)

        if kwargs.get("is_priority") and fee_schedule_dao.priority_fee and apply_filing_fees:
            fee_schedule.priority_fee = fee_schedule_dao.priority_fee.amount
        if kwargs.get("is_future_effective") and fee_schedule_dao.future_effective_fee and apply_filing_fees:
            fee_schedule.future_effective_fee = fee_schedule_dao.future_effective_fee.amount

        if kwargs.get("waive_fees"):
            fee_schedule.fee_amount = 0
            fee_schedule.priority_fee = 0
            fee_schedule.future_effective_fee = 0
            fee_schedule.service_fees = 0

        current_app.logger.debug(">get_fees_by_corp_type_and_filing_type")
        return fee_schedule

    @staticmethod
    def find_all(corp_type: str = None, filing_type_code: str = None, description: str = None):
        """Find all fee schedule by applying any filter."""
        current_app.logger.debug("<find_all")
        data = {"items": []}
        fee_schdules = FeeScheduleModel.find_all(
            corp_type_code=corp_type,
            filing_type_code=filing_type_code,
            description=description,
        )
        schdule_schema = FeeScheduleSchema()
        data["items"] = schdule_schema.dump(fee_schdules, many=True)
        current_app.logger.debug(">find_all")
        return data

    @staticmethod
    @user_context
    def calculate_service_fees(fee_schedule_model: FeeScheduleModel, account_fee: AccountFeeModel, **kwargs):
        """Calculate service_fees fees."""
        current_app.logger.debug("<calculate_service_fees")
        user: UserContext = kwargs["user"]

        service_fees: float = 0

        if (
            not user.is_staff()
            and not (user.is_system() and Role.EXCLUDE_SERVICE_FEES.value in user.roles)
            and fee_schedule_model.fee.amount > 0
            and fee_schedule_model.service_fee
        ):
            service_fee = (account_fee.service_fee if account_fee else None) or fee_schedule_model.service_fee
            if service_fee:
                service_fees = FeeCodeModel.find_by_code(service_fee.code).amount

        return service_fees

    @staticmethod
    def get_fee_details(product_code: str = None):
        """Get Products Fees -the cost of a filing and the list of filings."""
        current_app.logger.debug("<get_fee_details")
        data = {"items": []}
        products_fees = FeeScheduleModel.get_fee_details(product_code)
        for fee in products_fees:
            fee_details_schema = FeeDetailsSchema(
                corp_type=fee.corp_type,
                filing_type=fee.filing_type,
                corp_type_description=fee.corp_type_description,
                product_code=fee.product_code,
                service=fee.service,
                fee=fee.fee,
                service_charge=fee.service_charge,
                gst=fee.gst,
            )
            data["items"].append(fee_details_schema.to_dict())
        current_app.logger.debug(">get_fee_details")
        return data
