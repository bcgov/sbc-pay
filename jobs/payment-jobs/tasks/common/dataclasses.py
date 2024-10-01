# Copyright © 2022 Province of British Columbia
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
"""Common dataclasses for tasks, dataclasses allow for cleaner code with autocompletion in vscode."""
from decimal import Decimal

from dataclasses import dataclass
from typing import List, Optional
from dataclass_wizard import JSONWizard
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PartnerDisbursements as PartnerDisbursementModel
from pay_api.models import PaymentLineItem as LineItemModel
from pay_api.utils.enums import InvoiceStatus
from tasks.common.enums import PaymentDetailsGlStatus


@dataclass
class DisbursementLineItem:
    """DTO mapping for disbursement line item."""

    amount: Decimal
    flow_through: str
    description_identifier: str
    is_reversal: bool
    target_type: str
    identifier: int


@dataclass
class Disbursement:
    """DTO mapping for disbursement."""

    bcreg_distribution_code: DistributionCodeModel
    partner_distribution_code: DistributionCodeModel
    line_item: DisbursementLineItem
    target: InvoiceModel | PartnerDisbursementModel


@dataclass
class RefundData(JSONWizard):
    """Refund data from order status query."""

    refundglstatus: Optional[PaymentDetailsGlStatus]
    refundglerrormessage: str


@dataclass
class RevenueLine(JSONWizard):
    """Revenue line from order status query."""

    refund_data: List[RefundData]


@dataclass
class OrderStatus(JSONWizard):  # pylint:disable=too-many-instance-attributes
    """Return from order status query."""

    revenue: List[RevenueLine]


@dataclass
class APLine:
    """Used as a parameter to build AP inbox files."""

    total: float
    invoice_number: str
    line_number: int
    is_reversal: Optional[bool] = None
    distribution: Optional[str] = None

    @classmethod
    def from_invoice_and_line_item(cls, invoice: InvoiceModel, line_item: LineItemModel, line_number: int,
                                   distribution: str):
        """Build dataclass object from invoice."""
        # Note the invoice_date should be the payment_date in the future.
        return cls(total=line_item.total, invoice_number=invoice.id,
                   line_number=line_number,
                   is_reversal=invoice.invoice_status_code in
                   [InvoiceStatus.REFUNDED.value, InvoiceStatus.REFUND_REQUESTED.value, InvoiceStatus.CREDITED.value],
                   distribution=distribution)
