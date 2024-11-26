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

# TDI17 File Specifications
# One header record:
# .  Columns Len  Purpose
# .  1 -   1   1  Record type (always 1)
# .  2 -  16  15  "CREATION DATE: "
# . 17 -  24   8  File creation date in YYYYMMDD format
# . 25 -  41  17  "CREATION TIME:   "
# . 42 -  45   8  File creation time in HHMM format
# . 46 -  69  24  "DEPOSIT DATE(S) FROM:   "
# . 70 -  77   8  Starting deposit date in YYYYMMDD format
# . 78 -  89  12  " TO DATE :  "
# . 90 -  97   8  Ending deposit date in YYYYMMDD format
#
# Zero or more detail records:
# .  Columns Len  Purpose
# .  1 -   1   1  Record type (always 2)
# .  2 -   3   2  Ministry code
# .  4 -   7   4  Program code
# .  8 -  15   8  Deposit date in YYYYMMDD format
# . 16 -  20   5  Location ID
# . 21 -  24   4  Deposit time in YYYYMMDD format (optional)
# . 25 -  27   3  Transaction sequence number (optional)
# . 28 -  67  40  Transaction description
# . 68 -  80  13  Deposit amount in the specified currency, in cents
# . 81 -  82   2  Currency (blank = CAD, US = USD)
# . 83 -  95  13  Exchange adjustment amount, in cents
# . 96 - 108  13  Deposit amount in CAD, in cents
# .109 - 112   4  Destination bank number
# .113 - 121   9  Batch number (optional; specified only if posted to GL)
# .122 - 122   1  JV type (I = inter, J = intra; mandatory if JV batch specified)
# .123 - 131   9  JV number (mandatory if JV batch specified)
# .132 - 139   8  Transaction date (optional)
#
# One trailer record:
# .  Columns Len  Purpose
# .  1 -   1   1  Record type (always 7)
# .  2 -   7   6  Number of details (left zero filled)
# .  8 -  21  14  Total deposit amount, in CAD (left zero filled)
#
# All numbers are right justified and left padded with zeroes.
#
# In a money field, the rightmost character is either blank or a minus sign.

"""This manages the EFT base class."""
import decimal
from datetime import datetime
from typing import List, Tuple

from pay_queue.services.eft.eft_enums import EFTConstants
from pay_queue.services.eft.eft_errors import EFTError
from pay_queue.services.eft.eft_parse_error import EFTParseError


class EFTBase:
    """Defines the structure of the base class of an EFT record."""

    id: int  # Associated database primary key
    record_type: str  # Always 1 for header, 2 for transaction, 7 for trailer
    content: str
    index: int
    errors: List[EFTParseError]

    def __init__(self, content: str, index: int):
        """Return an EFT Base record."""
        self.content = content
        self.index = index
        self.errors = []

    def is_valid_length(self, length: int = EFTConstants.EXPECTED_LINE_LENGTH.value) -> bool:
        """Validate content is the expected length."""
        if self.content is None or len(self.content) != length:
            return False

        return True

    def validate_record_type(self, expected_record_type: str) -> bool:
        """Validate if the record type is the expected value."""
        if not self.record_type == expected_record_type:
            self.add_error(EFTParseError(EFTError.INVALID_RECORD_TYPE, self.index))

    def extract_value(self, start_index: int, end_index: int) -> str:
        """Extract and strip content value."""
        return self.content[start_index:end_index].strip()

    def parse_decimal(self, value: str, error: EFTError) -> decimal:
        """Try to parse decimal value from a string, return None if it fails and add an error."""
        try:
            # ends with blank or minus sign, handle the minus sign situation
            if value.endswith("-"):
                value = "-" + value[:-1]

            result = decimal.Decimal(str(value))
        except (ValueError, TypeError, decimal.InvalidOperation):
            result = None
            self.add_error(EFTParseError(error))

        return result

    def parse_int(self, value: str, error: EFTError) -> decimal:
        """Try to parse int value from a string, return None if it fails and add an error."""
        try:
            result = int(value)
        except (ValueError, TypeError):
            result = None
            self.add_error(EFTParseError(error))

        return result

    def parse_date(self, date_str: str, error: EFTError) -> decimal:
        """Try to parse date value from a string, return None if it fails and add an error."""
        try:
            result = datetime.strptime(date_str, EFTConstants.DATE_FORMAT.value)
        except (ValueError, TypeError):
            result = None
            self.add_error(EFTParseError(error))

        return result

    def parse_datetime(self, datetime_str: str, error: EFTError) -> decimal:
        """Try to parse date time value from a string, return None if it fails and add an error."""
        try:
            result = datetime.strptime(datetime_str, EFTConstants.DATE_TIME_FORMAT.value)
        except (ValueError, TypeError):
            result = None
            self.add_error(EFTParseError(error))

        return result

    def find_matching_pattern(self, patterns: Tuple, value: str) -> str:
        """Find matching pattern for a value."""
        for pattern in patterns:
            if value.startswith(pattern):
                return pattern
        return None

    def add_error(self, error: EFTParseError):
        """Add parse error to error array."""
        error.index = self.index
        self.errors.append(error)

    def has_errors(self) -> bool:
        """Return true if the error array has elements."""
        return len(self.errors) > 0

    def get_error_messages(self) -> List[str]:
        """Return a string array of the error messages."""
        return [error.message for error in self.errors]
