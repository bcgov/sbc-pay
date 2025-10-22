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
"""This manages the EFT Trailer record."""

import decimal

from pay_queue.services.eft.eft_base import EFTBase
from pay_queue.services.eft.eft_enums import EFTConstants
from pay_queue.services.eft.eft_errors import EFTError
from pay_queue.services.eft.eft_parse_error import EFTParseError


class EFTTrailer(EFTBase):
    """Defines the structure of the trailer of a received EFT file."""

    record_type: str  # Always 7
    number_of_details: int
    total_deposit_amount: decimal

    def __init__(self, content: str, index: int):
        """Return an EFT Trailer."""
        super().__init__(content, index)
        self._process()

    def _process(self):
        """Process and validate EFT Trailer string."""
        # Confirm line length is valid, skip if it is not, but add to error array
        if not self.is_valid_length():
            self.add_error(EFTParseError(EFTError.INVALID_LINE_LENGTH))
            return

        # Confirm record type is as expected
        self.record_type = self.extract_value(0, 1)
        self.validate_record_type(EFTConstants.TRAILER_RECORD_TYPE.value)

        # Confirm valid number of details value
        self.number_of_details = self.parse_int(self.extract_value(1, 7), EFTError.INVALID_NUMBER_OF_DETAILS)

        # Confirm valid total deposit amount value
        self.total_deposit_amount = self.parse_decimal(self.extract_value(7, 21), EFTError.INVALID_TOTAL_DEPOSIT_AMOUNT)
