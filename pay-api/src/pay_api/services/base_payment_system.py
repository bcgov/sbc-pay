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
"""Abstract class for payment system implementation."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class PaymentSystemService(ABC):  # pylint: disable=too-many-instance-attributes
    """Abstract base class for payment system.
    This class will list the operations implemented for any payment system.
    """

    def __init__(self):
        super(PaymentSystemService, self).__init__()

    @abstractmethod
    def create_account(self, name: str, account_info: Dict[str, Any]):
        pass

    @abstractmethod
    def create_invoice(self):
        pass

    @abstractmethod
    def update_invoice(self):
        pass

    @abstractmethod
    def get_receipt(self):
        pass

    @abstractmethod
    def get_payment_system_code(self):
        pass
