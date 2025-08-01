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
"""Constants."""

DEFAULT_JURISDICTION = "BC"
DEFAULT_COUNTRY = "CA"
DEFAULT_CITY = "NOT PROVIDED"
DEFAULT_ADDRESS_LINE_1 = "NOT PROVIDED"
DEFAULT_POSTAL_CODE = "NANANA"
DEFAULT_CURRENCY = "CAD"
RECEIPT_METHOD_PAD_DAILY = "BCR-PAD Daily"
RECEIPT_METHOD_PAD_STOP = "BCR-PAD Stop"

CFS_BATCH_SOURCE = "BC REG MANUAL_OTHER"
CFS_CM_BATCH_SOURCE = "MANUAL-OTHER"
CFS_CUST_TRX_TYPE = "BC_REGISTRIES"
CFS_CMS_TRX_TYPE = "BC_REG_CREDIT_MEMO"
CFS_TERM_NAME = "IMMEDIATE"
# PAYBC_MEMO_LINE_NAME = 'Test Memo Line'
CFS_LINE_TYPE = "LINE"
CFS_ADJ_ACTIVITY_NAME = "BC Registries Write Off"
CFS_CUSTOMER_PROFILE_CLASS = "BCR_CORP_PROFILE"
CFS_FAS_CUSTOMER_PROFILE_CLASS = "FAS_CORP_PROFILE"
CFS_RCPT_EFT_WIRE = "BC REG EFT Wire Cheque"
CFS_DRAWDOWN_BALANCE = "BC REG Drawdown Balance"
CFS_CASH_RCPT = "BC REG Cash Equivalent"

CFS_NSF_REVERSAL_REASON = "NSF"
CFS_PAYMENT_REVERSAL_REASON = "PAYMENT REVERSAL"

EDIT_ROLE = "edit"
VIEW_ROLE = "view"
MAKE_PAYMENT = "make_payment"
CHANGE_STATEMENT_SETTINGS = "change_statement_settings"

ALL_ALLOWED_ROLES = (EDIT_ROLE, VIEW_ROLE)

LEGISLATIVE_TIMEZONE = "America/Vancouver"
DT_SHORT_FORMAT = "%Y-%m-%d"
DT_FULL_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"

REFUND_SUCCESS_MESSAGES = {
    "PAD.APPROVED": "Your transaction has been cancelled. We will not request the initial payment from your bank.",
    "PAD.PAID": "Your transaction has been cancelled and a credit will be applied to your BC Registries account. "
    "There is a one day delay before the credit will show on your transactions / statements.",
    "ONLINE_BANKING.PAID": "Your transaction has been cancelled and a credit will be applied to your BC Registries "
    "account. There is a one day delay before the credit will show on your "
    "transactions / statements.",
    "DIRECT_PAY.PAID": "Your transaction has been cancelled and a refund has been requested.",
    "CC.PAID": "Your transaction has been cancelled and a credit will be applied to your BC Registries account. There "
    "is a one day delay before the credit will show on your transactions / statements.",
    "DRAWDOWN.PAID": "Your transaction has been cancelled and a refund has been requested.",
    "ROUTINGSLIP.REFUND_AUTHORIZED": "Routing slip refund has been authorised.",
    "ROUTINGSLIP.REFUND_REQUESTED": "Routing slip refund is requested.",
    "ROUTINGSLIP.ACTIVE": "Routing slip is active.",
    "INTERNAL.REFUND_REQUESTED": "Your transaction has been cancelled and a refund has been requested.",
    "INTERNAL.REFUNDED": "Your transaction has been cancelled and a refund has been done.",
}

TAX_CLASSIFICATION_GST = "GST"
