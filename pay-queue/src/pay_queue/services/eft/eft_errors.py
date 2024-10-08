# Copyright © 2023 Province of British Columbia
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
"""EFT error codes."""

from enum import Enum


class EFTError(Enum):
    """EFT Error Enum."""

    INVALID_LINE_LENGTH = "Invalid EFT file line length."
    INVALID_RECORD_TYPE = "Invalid Record Type."
    INVALID_CREATION_DATETIME = "Invalid header creation date time."
    INVALID_DEPOSIT_START_DATE = "Invalid header deposit start date."
    INVALID_DEPOSIT_END_DATE = "Invalid header deposit end date."
    INVALID_NUMBER_OF_DETAILS = "Invalid trailer number of details value."
    INVALID_TOTAL_DEPOSIT_AMOUNT = "Invalid trailer total deposit amount."
    INVALID_DEPOSIT_AMOUNT = "Invalid transaction deposit amount."
    INVALID_EXCHANGE_ADJ_AMOUNT = "Invalid transaction exchange adjustment amount."
    INVALID_DEPOSIT_AMOUNT_CAD = "Invalid transaction deposit amount CAD."
    INVALID_TRANSACTION_DATE = "Invalid transaction date."
    INVALID_DEPOSIT_DATETIME = "Invalid transaction deposit date time"
    ACCOUNT_SHORTNAME_REQUIRED = "Account shortname is missing from the transaction description."
