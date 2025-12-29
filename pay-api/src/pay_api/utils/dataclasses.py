# Copyright © 2025 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Data classes."""

from dataclasses import dataclass
from datetime import datetime

from attrs import define

from pay_api.utils.serializable import Serializable


@dataclass
class RoutingSlipSearch:
    """Routing slip search input parameters."""

    search_filter: dict
    page: int
    limit: int
    return_all: bool = False


@dataclass
class PurchaseHistorySearch:
    """Purchase History search input parameters."""

    auth_account_id: str
    search_filter: dict
    page: int
    limit: int
    filter_by_product: bool = False
    allowed_products: list[str] = None
    return_all: bool = False
    max_no_records: int = 0
    query_only: bool = False


@dataclass
class BaseActivityEvent:
    """Base activity event data class with common fields."""

    account_id: str
    source: str


@dataclass
class StatementIntervalChangeEvent(BaseActivityEvent):
    """Statement interval change data class."""

    old_frequency: str
    new_frequency: str
    effective_date: datetime = None


@dataclass
class StatementRecipientChangeEvent(BaseActivityEvent):
    """Statement recipient change data class."""

    old_recipients: list[str]
    new_recipients: list[str]
    statement_notification_email: bool


@dataclass
class AccountLockEvent(BaseActivityEvent):
    """Account lock event data class."""

    current_payment_method: str
    reason: str


@dataclass
class AccountUnlockEvent(BaseActivityEvent):
    """Account unlock event data class."""

    current_payment_method: str
    unlock_payment_method: str


@dataclass
class PaymentMethodChangeEvent(BaseActivityEvent):
    """Payment method change event data class."""

    old_method: str
    new_method: str


@dataclass
class PaymentInfoChangeEvent(BaseActivityEvent):
    """Payment info change event data class."""

    payment_method: str


@define
class ActivityLogData(Serializable):
    """Activity log data class."""

    actor_id: str
    action: str
    item_name: str
    item_id: str
    item_value: str
    org_id: str
    remote_addr: str
    created_at: str
    source: str
    item_type: str = "ACCOUNT"


@dataclass
class PaymentToken:
    """Payment token data class for event payloads."""

    id: int
    status_code: str
    filing_id: int | None
    corp_type_code: str
    payment_date: str | None = None
    refund_date: str | None = None
