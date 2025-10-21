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

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from operator import or_
from typing import Self

from flask import current_app
from sbc_common_components.tracing.service_tracing import ServiceTracing
from sqlalchemy import Date, func
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import literal
from sqlalchemy.sql.expression import and_, case

from pay_api.exceptions import BusinessException
from pay_api.models import AccountFee as AccountFeeModel
from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import FeeCode as FeeCodeModel
from pay_api.models import FeeDetailsSchema, FeeScheduleSchema, db
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import FilingType as FilingTypeModel
from pay_api.models import TaxRate as TaxRateModel
from pay_api.utils.constants import TAX_CLASSIFICATION_GST
from pay_api.utils.enums import Role
from pay_api.utils.errors import Error
from pay_api.utils.user_context import UserContext, user_context


@dataclass
class FeeCalculationParams:
    """Parameters for fee calculation."""

    quantity: int = 1
    is_priority: bool = False
    is_future_effective: bool = False
    waive_fees: bool = False
    apply_filing_fees: bool = True
    account_fee: AccountFeeModel = None
    variable_fee_amount: Decimal = None
    service_fee_already_applied: bool = False


@dataclass
class CalculatedFeeSchedule:
    """Calculated fee schedule. This has additional fields to the model calculated on the fly."""

    filing_type: FilingTypeModel
    filing_type_code: str
    corp_type_code: str
    fee_code: str
    fee_start_date: date
    fee_end_date: date
    variable: bool
    show_on_pricelist: bool
    gst_added: bool
    corp_type: CorpTypeModel
    fee: FeeCodeModel
    distribution_codes: list[DistributionCodeModel]
    quantity: int = 1
    description: str = ""
    priority_fee: Decimal = Decimal("0.00")
    future_effective_fee: Decimal = Decimal("0.00")
    pst: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    fee_amount: Decimal = Decimal("0.00")
    total_excluding_service_fees: Decimal = Decimal("0.00")
    fee_schedule_id: int | None = None
    waived_fee_amount: Decimal = Decimal("0.00")
    service_fees_gst: Decimal = Decimal("0.00")
    statutory_fees_gst: Decimal = Decimal("0.00")
    service_fees: float = Decimal("0.00")
    apply_filing_fees: bool = True

    @classmethod
    def from_dao(cls, row: FeeScheduleModel) -> Self:
        """Create a CalculatedFeeSchedule from a DAO."""
        return cls(
            fee_schedule_id=row.fee_schedule_id,
            filing_type=row.filing_type,
            filing_type_code=row.filing_type_code,
            corp_type_code=row.corp_type_code,
            fee_code=row.fee_code,
            fee_start_date=row.fee_start_date,
            fee_end_date=row.fee_end_date,
            fee_amount=row.fee.amount if row.fee else 0,
            pst=0,
            total=0,
            variable=row.variable,
            show_on_pricelist=row.show_on_pricelist,
            gst_added=row.gst_added,
            corp_type=row.corp_type,
            fee=row.fee,
            distribution_codes=[],
            # Needs to be loaded in for calculate_service_fees_check
            service_fees=row.service_fee.amount if row.service_fee else 0,
            future_effective_fee=row.future_effective_fee.amount if row.future_effective_fee else 0,
            priority_fee=row.priority_fee.amount if row.priority_fee else 0,
            waived_fee_amount=0,
            total_excluding_service_fees=0,
        )

    def calculate_singular_fee(self, params: FeeCalculationParams = None):
        """Create a CalculatedFeeSchedule from a row."""
        if not params.apply_filing_fees:
            self.fee_amount = 0
            self.waived_fee_amount = 0

        self.service_fees = FeeSchedule.calculate_service_fees(self, params.account_fee)

        if params.is_priority and self.priority_fee and params.apply_filing_fees:
            self.priority_fee = self.priority_fee
        else:
            self.priority_fee = 0

        if params.is_future_effective and self.future_effective_fee and params.apply_filing_fees:
            self.future_effective_fee = self.future_effective_fee
        else:
            self.future_effective_fee = 0

        if params.waive_fees:
            if not self.variable:
                self.waived_fee_amount = self.fee_amount + self.priority_fee + self.future_effective_fee
            self.fee_amount = 0
            self.priority_fee = 0
            self.future_effective_fee = 0
            self.service_fees = 0
            self.service_fees_gst = 0
            self.statutory_fees_gst = 0

        self.quantity = params.quantity or 1

        if self.quantity > 1:
            self.fee_amount = self.fee_amount * self.quantity

        if self.variable and params and params.variable_fee_amount is not None:
            self.fee_amount = params.variable_fee_amount

        self.total_excluding_service_fees = self.fee_amount + self.priority_fee + self.future_effective_fee

        if self.gst_added and not params.waive_fees:
            self.service_fees_gst = round(
                self.service_fees * TaxRateModel.get_gst_effective_rate(datetime.now(tz=UTC)), 2
            )
            self.statutory_fees_gst = round(
                self.total_excluding_service_fees * TaxRateModel.get_gst_effective_rate(datetime.now(tz=UTC)), 2
            )

        self.total = (
            self.fee_amount
            + self.priority_fee
            + self.future_effective_fee
            + self.service_fees
            + self.service_fees_gst
            + self.statutory_fees_gst
            + self.pst
        )

        if params.service_fee_already_applied:
            self.total -= self.service_fees + self.service_fees_gst
            self.service_fees = 0
            self.service_fees_gst = 0
        self.description = self.filing_type.description
        return self

    def asdict(self):
        """Return the Calculated Fee Schedule as a python dict."""
        d = {
            "filing_type": self.filing_type.description,
            "filing_type_code": self.filing_type_code,
            "filing_fees": float(self.fee_amount),
            "priority_fees": float(self.priority_fee),
            "future_effective_fees": float(self.future_effective_fee),
            "tax": {"gst": float(self.service_fees_gst + self.statutory_fees_gst), "pst": float(self.pst)},
            "total": float(self.total),
            "service_fees": float(self.service_fees),
            "processing_fees": 0.0,
        }
        return d


@ServiceTracing.trace(ServiceTracing.enable_tracing, ServiceTracing.should_be_tracing)
class FeeSchedule:
    """Service to manage Fee related operations."""

    @classmethod
    @user_context
    def find_by_corp_type_and_filing_type(  # pylint: disable=too-many-arguments
        cls, corp_type: str, filing_type_code: str, valid_date: date, **kwargs
    ) -> CalculatedFeeSchedule:
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

        calculated_fs = CalculatedFeeSchedule.from_dao(fee_schedule_dao)

        account_fee = AccountFeeModel.find_by_auth_account_id_and_corp_type(user.account_id, corp_type)

        params = FeeCalculationParams(
            quantity=kwargs.get("quantity", 1),
            is_priority=kwargs.get("is_priority", False),
            is_future_effective=kwargs.get("is_future_effective", False),
            waive_fees=kwargs.get("waive_fees", False),
            apply_filing_fees=account_fee.apply_filing_fees if account_fee else True,
            account_fee=account_fee,
            variable_fee_amount=kwargs.get("variable_fee_amount"),
            service_fee_already_applied=kwargs.get("service_fee_already_applied", False),
        )

        calculated_fs = calculated_fs.calculate_singular_fee(params)

        current_app.logger.debug(">get_fees_by_corp_type_and_filing_type")
        return calculated_fs

    @staticmethod
    def find_all(corp_type_code: str = None, filing_type_code: str = None, description: str = None):
        """Find all fee schedule by applying any filter."""
        current_app.logger.debug("<find_all")
        data = {"items": []}

        valid_date = datetime.now(tz=UTC).date()
        query = (
            db.session.query(FeeScheduleModel)
            .filter(FeeScheduleModel.fee_start_date <= valid_date)
            .filter((FeeScheduleModel.fee_end_date.is_(None)) | (FeeScheduleModel.fee_end_date >= valid_date))
        )

        if filing_type_code:
            query = query.filter_by(filing_type_code=filing_type_code)

        if corp_type_code:
            query = query.filter_by(corp_type_code=corp_type_code)

        if description:
            descriptions = description.replace(" ", "%")
            query = query.join(CorpTypeModel, CorpTypeModel.code == FeeScheduleModel.corp_type_code).join(
                FilingTypeModel, FilingTypeModel.code == FeeScheduleModel.filing_type_code
            )
            query = query.filter(
                or_(
                    func.lower(FilingTypeModel.description).contains(descriptions.lower()),
                    func.lower(CorpTypeModel.description).contains(descriptions.lower()),
                )
            )

        fee_schedules = query.all()
        schedule_schema = FeeScheduleSchema()
        data["items"] = schedule_schema.dump(fee_schedules, many=True)
        current_app.logger.debug(">find_all")
        return data

    @staticmethod
    @user_context
    def calculate_service_fees(calculated_fee_schedule: CalculatedFeeSchedule, account_fee: AccountFeeModel, **kwargs):
        """Calculate service_fees fees."""
        current_app.logger.debug("<calculate_service_fees")
        user: UserContext = kwargs["user"]

        service_fees: float = 0

        if (
            not user.is_staff()
            and not (user.is_system() and Role.EXCLUDE_SERVICE_FEES.value in user.roles)
            and calculated_fee_schedule.fee
            and calculated_fee_schedule.fee.amount > 0
            and calculated_fee_schedule.service_fees
        ):
            account_service_fee = account_fee.service_fee if account_fee else None
            if account_service_fee:
                service_fees = FeeCodeModel.find_by_code(account_service_fee.code).amount
            else:
                service_fees = calculated_fee_schedule.service_fees

        return service_fees

    @staticmethod
    def get_gst_amount_expression(amount_expr):
        """Return calculated GST amount."""
        return func.coalesce(
            case(
                (
                    FeeScheduleModel.gst_added.is_(True),
                    func.round(TaxRateModel.rate * func.coalesce(amount_expr, 0), 2),
                ),
                else_=0,
            ),
            0,
        )

    @staticmethod
    def get_gst_expressions(main_fee_code, service_fee_code):
        """Return GST break down amounts."""
        main_fee_gst = FeeSchedule.get_gst_amount_expression(main_fee_code.amount).label("main_fee_gst")
        service_fee_gst = FeeSchedule.get_gst_amount_expression(service_fee_code.amount).label("service_fee_gst")
        total_gst = FeeSchedule.get_gst_amount_expression(
            func.coalesce(main_fee_code.amount, 0) + func.coalesce(service_fee_code.amount, 0)
        ).label("total_gst")
        return main_fee_gst, service_fee_gst, total_gst

    @staticmethod
    def get_fee_details(product_code: str = None) -> dict:
        """Get Products Fees -the cost of a filing and the list of filings."""
        current_app.logger.debug("<get_fee_details")
        data = {"items": []}
        main_fee_code = aliased(FeeCodeModel)
        service_fee_code = aliased(FeeCodeModel)

        current_date = datetime.now(tz=UTC).date()
        infinity_date = literal("infinity").cast(Date)
        query = (
            db.session.query(
                CorpTypeModel.code.label("corp_type"),
                FilingTypeModel.code.label("filing_type"),
                CorpTypeModel.description.label("corp_type_description"),
                CorpTypeModel.product.label("product_code"),
                FilingTypeModel.description.label("service"),
                func.coalesce(main_fee_code.amount, 0).label("fee"),
                func.coalesce(service_fee_code.amount, 0).label("service_charge"),
                *FeeSchedule.get_gst_expressions(main_fee_code, service_fee_code),
                FeeScheduleModel.variable,
            )
            .select_from(FeeScheduleModel)
            .join(CorpTypeModel, FeeScheduleModel.corp_type_code == CorpTypeModel.code)
            .join(FilingTypeModel, FeeScheduleModel.filing_type_code == FilingTypeModel.code)
            .outerjoin(main_fee_code, FeeScheduleModel.fee_code == main_fee_code.code)
            .outerjoin(service_fee_code, FeeScheduleModel.service_fee_code == service_fee_code.code)
            .outerjoin(
                TaxRateModel,
                and_(
                    FeeScheduleModel.gst_added.is_(True),
                    TaxRateModel.tax_type == TAX_CLASSIFICATION_GST,
                    TaxRateModel.start_date <= func.coalesce(FeeScheduleModel.fee_end_date, infinity_date),
                    FeeScheduleModel.fee_start_date <= func.coalesce(TaxRateModel.effective_end_date, infinity_date),
                ),
            )
            .filter(FeeScheduleModel.fee_start_date <= current_date)
            .filter(FeeScheduleModel.fee_end_date.is_(None) | (FeeScheduleModel.fee_end_date >= current_date))
            .filter(CorpTypeModel.product.is_not(None))
            .filter(FeeScheduleModel.show_on_pricelist.is_(True))
        )

        if product_code:
            query = query.filter(CorpTypeModel.product == product_code)

        products_fees = query.all()
        for fee in products_fees:
            fee_details_schema = FeeDetailsSchema(
                corp_type=fee.corp_type,
                filing_type=fee.filing_type,
                corp_type_description=fee.corp_type_description,
                product_code=fee.product_code,
                service=fee.service,
                fee=fee.fee,
                service_charge=fee.service_charge,
                gst=fee.total_gst,
                fee_gst=fee.main_fee_gst,
                service_charge_gst=fee.service_fee_gst,
                variable=fee.variable,
            )
            data["items"].append(fee_details_schema.to_dict())
        current_app.logger.debug(">get_fee_details")
        return data

    @staticmethod
    def calculate_fees(corp_type, filing_info) -> list[CalculatedFeeSchedule]:
        """Calculate and return the fees based on the filing type codes."""
        fees = []
        service_fee_already_applied: bool = False
        for filing_type_info in filing_info.get("filingTypes"):
            current_app.logger.debug(f"Getting fees for {filing_type_info.get('filingTypeCode')} ")
            calculated_fee = FeeSchedule.find_by_corp_type_and_filing_type(
                corp_type=corp_type,
                filing_type_code=filing_type_info.get("filingTypeCode", None),
                valid_date=filing_info.get("date", None),
                service_fee_already_applied=service_fee_already_applied,
                jurisdiction=None,
                is_priority=filing_type_info.get("priority"),
                is_future_effective=filing_type_info.get("futureEffective"),
                waive_fees=filing_type_info.get("waiveFees"),
                quantity=filing_type_info.get("quantity"),
                variable_fee_amount=Decimal(str(filing_type_info.get("fee", 0)))
                if filing_type_info.get("fee")
                else None,
            )
            if calculated_fee.service_fees > 0:
                service_fee_already_applied = True

            if filing_type_info.get("filingDescription"):
                calculated_fee.description = filing_type_info.get("filingDescription")

            fees.append(calculated_fee)
        return fees
