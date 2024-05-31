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
"""Service to manage Payment Line Items."""

from decimal import Decimal
from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.services.fee_schedule import FeeSchedule
from pay_api.utils.enums import LineItemStatus, Role
from pay_api.utils.errors import Error
from pay_api.utils.user_context import UserContext, user_context


class PaymentLineItem:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Service to manage Payment Line Item operations."""

    def __init__(self):
        """Return a User Service object."""
        self.__dao = None
        self._id: int = None
        self._invoice_id: int = None
        self._filing_fees = None
        self._fee_schedule_id: int = None
        self._priority_fees = None
        self._future_effective_fees = None
        self._description: str = None
        self._gst = None
        self._pst = None
        self._total = None
        self._quantity: int = 1
        self._line_item_status_code: str = None
        self._waived_fees = Decimal('0')
        self._waived_by: str = None
        self._fee_distribution_id: int = None
        self._fee_distribution: DistributionCodeModel = None
        self._service_fees = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = PaymentLineItemModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value
        self.id: int = self._dao.id
        self.invoice_id: int = self._dao.invoice_id
        self.filing_fees: Decimal = self._dao.filing_fees
        self.fee_schedule_id: int = self._dao.fee_schedule_id
        self.priority_fees: Decimal = self._dao.priority_fees
        self.future_effective_fees: Decimal = self._dao.future_effective_fees
        self.description: str = self._dao.description
        self.gst: Decimal = self._dao.gst
        self.pst: Decimal = self._dao.pst
        self.total: Decimal = self._dao.total
        self.quantity: int = self._dao.quantity
        self.line_item_status_code: str = self._dao.line_item_status_code
        self.waived_fees: Decimal = self._dao.waived_fees
        self.waived_by: str = self._dao.waived_by
        self.fee_distribution_id: int = self._dao.fee_distribution_id
        self.service_fees: Decimal = self._dao.service_fees

    @property
    def id(self):
        """Return the _id."""
        return self._id

    @property
    def invoice_id(self):
        """Return the _invoice_id."""
        return self._invoice_id

    @id.setter
    def id(self, value: int):
        """Set the id."""
        self._id = value
        self._dao.id = value

    @invoice_id.setter
    def invoice_id(self, value: int):
        """Set the invoice_id."""
        self._invoice_id = value
        self._dao.invoice_id = value

    @property
    def filing_fees(self):
        """Return the _filing_fees."""
        return self._filing_fees

    @filing_fees.setter
    def filing_fees(self, value: Decimal):
        """Set the filing_fees."""
        self._filing_fees = value
        self._dao.filing_fees = value

    @property
    def fee_schedule_id(self):
        """Return the _fee_schedule_id."""
        return self._fee_schedule_id

    @property
    def priority_fees(self):
        """Return the _priority_fees."""
        return self._priority_fees

    @fee_schedule_id.setter
    def fee_schedule_id(self, value: int):
        """Set the fee_schedule_id."""
        self._fee_schedule_id = value
        self._dao.fee_schedule_id = value

    @priority_fees.setter
    def priority_fees(self, value: Decimal):
        """Set the priority_fees."""
        self._priority_fees = value
        self._dao.priority_fees = value

    @property
    def future_effective_fees(self):
        """Return the _future_effective_fees."""
        return self._future_effective_fees

    @future_effective_fees.setter
    def future_effective_fees(self, value: Decimal):
        """Set the future_effective_fees."""
        self._future_effective_fees = value
        self._dao.future_effective_fees = value

    @property
    def description(self):
        """Return the _description."""
        return self._description

    @description.setter
    def description(self, value: str):
        """Set the description."""
        self._description = value
        self._dao.description = value

    @property
    def gst(self):
        """Return the _gst."""
        return self._gst

    @gst.setter
    def gst(self, value: Decimal):
        """Set the gst."""
        self._gst = value
        self._dao.gst = value

    @property
    def pst(self):
        """Return the _pst."""
        return self._pst

    @pst.setter
    def pst(self, value: Decimal):
        """Set the pst."""
        self._pst = value
        self._dao.pst = value

    @property
    def total(self):
        """Return the _total."""
        return self._total

    @property
    def quantity(self):
        """Return the _quantity."""
        return self._quantity

    @total.setter
    def total(self, value: Decimal):
        """Set the total."""
        self._total = value
        self._dao.total = value

    @quantity.setter
    def quantity(self, value: int):
        """Set the quantity."""
        self._quantity = value
        self._dao.quantity = value

    @property
    def line_item_status_code(self):
        """Return the line_item_status_code."""
        return self._line_item_status_code

    @line_item_status_code.setter
    def line_item_status_code(self, value: str):
        """Set the line_item_status_code."""
        self._line_item_status_code = value
        self._dao.line_item_status_code = value

    @property
    def waived_fees(self):
        """Return the waived_fees."""
        return self._waived_fees

    @waived_fees.setter
    def waived_fees(self, value: Decimal):
        """Set the waived_fees."""
        self._waived_fees = value
        self._dao.waived_fees = value

    @property
    def waived_by(self):
        """Return the waived_by."""
        return self._waived_by

    @waived_by.setter
    def waived_by(self, value: str):
        """Set the waived_by."""
        self._waived_by = value
        self._dao.waived_by = value

    @property
    def filing_type_code(self):
        """Return the filing_type_code."""
        return self._dao.fee_schedule.filing_type_code

    @property
    def fee_distribution_id(self):
        """Return the fee_distribution_id."""
        return self._fee_distribution_id

    @fee_distribution_id.setter
    def fee_distribution_id(self, value: int):
        """Set the fee_distribution_id."""
        self._fee_distribution_id = value
        self._dao.fee_distribution_id = value

    @property
    def fee_distribution(self):
        """Return the fee_distribution."""
        return self._fee_distribution

    @fee_distribution.setter
    def fee_distribution(self, value: DistributionCodeModel):
        """Set the fee_distribution."""
        self._fee_distribution = value

    @property
    def service_fees(self):
        """Return the service_fees."""
        return self._service_fees

    @service_fees.setter
    def service_fees(self, value: Decimal):
        """Set the service_fees."""
        self._service_fees = value
        self._dao.service_fees = value

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    @staticmethod
    @user_context
    def create(invoice_id: int, fee: FeeSchedule, **kwargs):
        """Create Payment Line Item record."""
        current_app.logger.debug('<create')
        user: UserContext = kwargs['user']
        p = PaymentLineItem()
        p.invoice_id = invoice_id
        p.total = fee.total_excluding_service_fees
        p.fee_schedule_id = fee.fee_schedule_id
        p.description = fee.description
        p.filing_fees = fee.fee_amount
        p.gst = fee.gst
        p.priority_fees = fee.priority_fee
        p.pst = fee.pst
        p.future_effective_fees = fee.future_effective_fee
        p.quantity = fee.quantity if fee.quantity else 1
        p.line_item_status_code = LineItemStatus.ACTIVE.value
        p.waived_fees = fee.waived_fee_amount
        p.service_fees = fee.service_fees

        # Set distribution details to line item
        distribution_code = None
        if p.total > 0 or p.service_fees > 0:
            distribution_code = DistributionCodeModel.find_by_active_for_fee_schedule(fee.fee_schedule_id)
            p.fee_distribution_id = distribution_code.distribution_code_id

        if fee.waived_fee_amount > 0:
            if user.has_role(Role.STAFF.value):
                p.waived_by = user.user_name
            else:
                raise BusinessException(Error.FEE_OVERRIDE_NOT_ALLOWED)

        p_dao = p.flush()

        p = PaymentLineItem()
        p._dao = p_dao  # pylint: disable=protected-access

        # Set distribution model to avoid more queries to DB
        p.fee_distribution = distribution_code
        current_app.logger.debug('>create')
        return p

    @staticmethod
    def find_by_id(line_id: int):
        """Find by line id."""
        line_dao = PaymentLineItemModel.find_by_id(line_id)

        line = PaymentLineItem()
        line._dao = line_dao  # pylint: disable=protected-access

        current_app.logger.debug('>find_by_id')
        return line
