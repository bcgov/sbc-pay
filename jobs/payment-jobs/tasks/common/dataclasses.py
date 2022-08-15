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

from dataclasses import dataclass
from typing import List

from tasks.common.enums import PaymentDetailsGlStatus, PaymentDetailsStatus


@dataclass
class RevenueLine:
    """Revenue line from order status query."""

    linenumber: str
    revenueaccount: str
    revenueamount: str
    glstatus: str
    glerrormessage: str
    refundglstatus: str
    refundglerrormessage: str


@dataclass
class OrderStatus:
    """Return from order status query."""

    pbcrefnumber: str
    trnnumber: str
    trndate: str
    trnamount: str
    paymentstatus: str
    trnorderid: str
    refundstatus: PaymentDetailsStatus
    revenue: List[RevenueLine]
    refundglstatus: PaymentDetailsGlStatus
    refundglerrormessage: str
