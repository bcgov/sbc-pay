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
"""Service to manage Payment Line Items."""

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.services.fee_schedule import FeeSchedule
from pay_api.utils.enums import LineItemStatus, Role
from pay_api.utils.errors import Error
from pay_api.utils.user_context import UserContext, user_context


class PaymentLineItem:
    """Service to manage Payment Line Item operations."""

    @staticmethod
    @user_context
    def create(invoice_id: int, fee: FeeSchedule, **kwargs):
        """Create Payment Line Item record."""
        current_app.logger.debug("<create")
        user: UserContext = kwargs["user"]
        p = PaymentLineItemModel()
        p.invoice_id = invoice_id
        p.total = fee.total_excluding_service_fees
        p.fee_schedule_id = fee.fee_schedule_id
        p.description = fee.description
        p.filing_fees = fee.fee_amount
        p.priority_fees = fee.priority_fee
        p.pst = fee.pst
        p.future_effective_fees = fee.future_effective_fee
        p.quantity = fee.quantity if fee.quantity else 1
        p.line_item_status_code = LineItemStatus.ACTIVE.value
        p.waived_fees = fee.waived_fee_amount
        p.service_fees = fee.service_fees
        p.service_fees_gst = fee.service_fees_gst
        p.statutory_fees_gst = fee.statutory_fees_gst

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

        p.flush()

        # Set distribution model to avoid more queries to DB
        p.fee_distribution = distribution_code
        current_app.logger.debug(">create")
        return p

    @staticmethod
    def find_by_id(line_id: int):
        """Find by line id."""
        return PaymentLineItemModel.find_by_id(line_id)
