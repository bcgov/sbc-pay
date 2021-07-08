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
    REFUNDED = 'REFUNDED'
    FAILED = 'FAILED'


class InvoiceStatus(Enum):
    """Invoice status codes."""

    CREATED = 'CREATED'
    APPROVED = 'APPROVED'
    PAID = 'PAID'
    DELETED = 'DELETED'
    UPDATE_REVENUE_ACCOUNT = 'GL_UPDATED'
    DELETE_ACCEPTED = 'DELETE_ACCEPTED'
    SETTLEMENT_SCHEDULED = 'SETTLEMENT_SCHED'
    REFUND_REQUESTED = 'REFUND_REQUESTED'
    PARTIAL = 'PARTIAL_PAID'


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
    CGI = 'CGI'
    FAS = 'FAS'


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
    CASH = 'CASH'
    CHEQUE = 'CHEQUE'


class Role(Enum):
    """User Role."""

    STAFF = 'staff'
    VIEWER = 'view'
    EDITOR = 'edit'
    SYSTEM = 'system'
    MANAGE_GL_CODES = 'manage_gl_codes'
    PUBLIC_USER = 'public_user'
    EXCLUDE_SERVICE_FEES = 'exclude_service_fees'
    CREATE_CREDITS = 'create_credits'
    MANAGE_ACCOUNTS = 'manage_accounts'
    FAS_USER = 'fas_user'
    FAS_EDITOR = 'fas_edit'


class Code(Enum):
    """Code value keys."""

    ERROR = 'errors'
    INVOICE_STATUS = 'invoice_statuses'
    CORP_TYPE = 'corp_types'
    FEE_CODE = 'fee_codes'


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
    PENDING_PAD_ACTIVATION = 'PENDING_PAD_ACTIVATION'
    ACTIVE = 'ACTIVE'
    INACTIVE = 'INACTIVE'
    FREEZE = 'FREEZE'


class CorpType(Enum):
    """Corp Type."""

    NRO = 'NRO'
    PPR = 'PPR'
    VS = 'VS'


class DisbursementStatus(Enum):
    """Disbursement status codes."""

    UPLOADED = 'UPLOADED'
    ACKNOWLEDGED = 'ACKNOWLEDGED'
    ERRORED = 'ERRORED'
    COMPLETED = 'COMPLETED'


class Product(Enum):
    """Product."""

    BUSINESS = 'BUSINESS'


class RoutingSlipStatus(Enum):
    """Routing slip statuses."""

    ACTIVE = 'ACTIVE'
    COMPLETE = 'COMPLETE'
    BOUNCED = 'BOUNCED'
    NSF = 'NSF'
    REFUND = 'REFUND'
    LAST = 'LAST'
