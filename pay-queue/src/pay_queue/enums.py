# Copyright © 2024 Province of British Columbia
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
"""Enum definitions."""
from enum import Enum


class SourceTransaction(Enum):
    """Source Transaction types."""

    PAD = 'BCR-PAD Daily'
    ONLINE_BANKING = 'BCR Online Banking Payments'
    CREDIT_MEMO = 'CM'
    ADJUSTMENT = 'BCR-ADJ'
    EFT_WIRE = 'BC REG EFT Wire Cheque'


class RecordType(Enum):
    """Record types."""

    PAD = 'PADP'
    PAYR = 'PAYR'
    BOLP = 'BOLP'
    CMAP = 'CMAP'
    ADJS = 'ADJS'
    ONAC = 'ONAC'
    ONAP = 'ONAP'
    EFTP = 'EFTP'
    PADR = 'PADR'
    DRWP = 'DRWP'


class Column(Enum):
    """Column Types."""

    RECORD_TYPE = 'Record type'
    SOURCE_TXN = 'Source transaction type'
    SOURCE_TXN_NO = 'Source Transaction Number'
    APP_ID = 'Application Id'
    APP_DATE = 'Application Date'
    APP_AMOUNT = 'Application amount'
    CUSTOMER_ACC = 'Customer Account'
    TARGET_TXN = 'Target transaction type'
    TARGET_TXN_NO = 'Target transaction Number'
    TARGET_TXN_ORIGINAL = 'Target Transaction Original amount'
    TARGET_TXN_OUTSTANDING = 'Target Transaction Outstanding Amount'
    TARGET_TXN_STATUS = 'Target transaction status'
    REVERSAL_REASON_CODE = 'Reversal Reason code'
    REVERSAL_REASON_DESC = 'Reversal reason desc'


class Status(Enum):
    """Target Transaction Status."""

    PAID = 'Fully PAID'
    NOT_PAID = 'Not PAID'
    ON_ACC = 'On Account'
    PARTIAL = 'Partially PAID'


class TargetTransaction(Enum):
    """Target Transaction."""

    INV = 'INV'
    DEBIT_MEMO = 'DM'
    CREDIT_MEMO = 'CM'
    RECEIPT = 'RECEIPT'
