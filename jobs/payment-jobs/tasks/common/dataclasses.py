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
from dataclasses import dataclass
from typing import List
from dataclass_wizard import JSONWizard

from tasks.common.enums import PaymentDetailsGlStatus, PaymentDetailsStatus


@dataclass
class RevenueLine(JSONWizard):
    """Revenue line from order status query."""

    refundglstatus: PaymentDetailsGlStatus
    refundglerrormessage: str


@dataclass
class OrderStatus(JSONWizard):  # pylint:disable=too-many-instance-attributes
    """Return from order status query."""

    refundstatus: PaymentDetailsStatus
    revenue: List[RevenueLine]
