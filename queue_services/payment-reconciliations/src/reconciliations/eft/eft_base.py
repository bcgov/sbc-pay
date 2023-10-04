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
"""This manages the EFT base class."""
import decimal
from datetime import datetime

from reconciliations.eft.eft_enums import EFTConstants
from reconciliations.eft.eft_errors import EFTError
from reconciliations.eft.eft_parse_error import EFTParseError


class EFTBase:
    """Defines the structure of the base class of an EFT record."""

    record_type: str  # Always 1 for header, 2 for transaction, 7 for trailer
    content: str
    index: int
    errors: [EFTParseError]

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

    def parse_decimal(self, value: str, error: EFTError) -> decimal:
        """Try to parse decimal value from a string, return None if it fails and add an error."""
        try:
            # ends with blank or minus sign, handle the minus sign situation
            if value.endswith('-'):
                value = '-' + value[:-1]

            result = decimal.Decimal(value)
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

    def add_error(self, error: EFTParseError):
        """Add parse error to error array."""
        error.index = self.index
        self.errors.append(error)

    def has_errors(self) -> bool:
        """Return true if the error array has elements."""
        return len(self.errors) > 0

    def get_error_messages(self) -> [str]:
        """Return a string array of the error messages."""
        return [error.message for error in self.errors]
