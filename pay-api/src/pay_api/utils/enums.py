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
"""Enum definitions."""
from enum import Enum


class AuthHeaderType(Enum):
    """Authorization header types."""

    BASIC = 'Basic {}'
    BEARER = 'Bearer {}'


class ContentType(Enum):
    """Http Content Types."""

    JSON = 'application/json'
    FORM_URL_ENCODED = 'application/x-www-form-urlencoded'
    CSV = 'text/csv'
    PDF = 'application/pdf'


class PaymentStatus(Enum):
    """Payment status codes."""

    CREATED = 'CREATED'
    COMPLETED = 'COMPLETED'
    DELETED = 'DELETED'


class InvoiceStatus(Enum):
    """Invoice status codes."""

    CREATED = 'CREATED'
    PAID = 'PAID'
    DELETED = 'DELETED'
    UPDATE_REVENUE_ACCOUNT = 'GL_UPDATED'
    DELETE_ACCEPTED = 'DELETE_ACCEPTED'


class TransactionStatus(Enum):
    """Transaction status codes."""

    CREATED = 'CREATED'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'
    EVENT_FAILED = 'EVENT_FAILED'


class LineItemStatus(Enum):
    """Line Item status codes."""

    ACTIVE = 'ACTIVE'
    CANCELLED = 'CANCELLED'


class InvoiceReferenceStatus(Enum):
    """Line Invoice Reference status codes."""

    ACTIVE = 'ACTIVE'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'


class PaymentSystem(Enum):
    """Payment System Codes."""

    PAYBC = 'PAYBC'
    BCOL = 'BCOL'
    INTERNAL = 'INTERNAL'


class PaymentMethod(Enum):
    """Payment Method Codes."""

    CC = 'CC'
    DRAWDOWN = 'DRAWDOWN'
    INTERNAL = 'INTERNAL'
    DIRECT_PAY = 'DIRECT_PAY'
    EFT = 'EFT'
    WIRE = 'WIRE'
    ONLINE_BANKING = 'ONLINE_BANKING'
    PAD = 'PAD'
    EJV = 'EJV'


class Role(Enum):
    """User Role."""

    STAFF = 'staff'
    VIEWER = 'view'
    EDITOR = 'edit'
    SYSTEM = 'system'
    STAFF_ADMIN = 'admin'
    PUBLIC_USER = 'public_user'
    EXCLUDE_SERVICE_FEES = 'exclude_service_fees'


class Code(Enum):
    """Code value keys."""

    ERROR = 'errors'
    INVOICE_STATUS = 'invoice_statuses'


class AccountType(Enum):
    """Account types."""

    BASIC = 'BASIC'
    PREMIUM = 'PREMIUM'


class StatementFrequency(Enum):
    """Statement frequency."""

    DAILY = 'DAILY'
    WEEKLY = 'WEEKLY'
    MONTHLY = 'MONTHLY'

    @staticmethod
    def default_frequency():
        """Return the default frequency for statements."""
        return StatementFrequency.WEEKLY


class NotificationStatus(Enum):
    """Mail notification Status."""

    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    SUCCESS = 'SUCCESS'
    SKIP = 'SKIP'
    FAILED = 'FAILED'


class CfsAccountStatus(Enum):
    """Cfs Account Status."""

    PENDING = 'PENDING'
    ACTIVE = 'ACTIVE'
    INACTIVE = 'INACTIVE'
    FREEZE = 'FREEZE'
