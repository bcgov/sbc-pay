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
"""This manages the EFT Header record."""
from datetime import datetime

from pay_queue.services.eft.eft_base import EFTBase
from pay_queue.services.eft.eft_enums import EFTConstants
from pay_queue.services.eft.eft_errors import EFTError
from pay_queue.services.eft.eft_parse_error import EFTParseError


class EFTHeader(EFTBase):
    """Defines the structure of the header of a received EFT file."""

    creation_datetime: datetime
    starting_deposit_date: datetime
    ending_deposit_date: datetime

    def __init__(self, content: str, index: int):
        """Return an EFT Header."""
        super().__init__(content, index)
        self._process()

    def _process(self):
        """Process and validate EFT Header string."""
        # Confirm line length is valid, skip if it is not, but add to error array
        if not self.is_valid_length():
            self.add_error(EFTParseError(EFTError.INVALID_LINE_LENGTH))
            return

        # Confirm record type is as expected
        self.record_type = self.extract_value(0, 1)
        self.validate_record_type(EFTConstants.HEADER_RECORD_TYPE.value)

        # Confirm valid file creation datetime
        self.creation_datetime = self.parse_datetime(
            self.extract_value(16, 24) + self.extract_value(41, 45),
            EFTError.INVALID_CREATION_DATETIME,
        )

        # Confirm valid deposit dates
        self.starting_deposit_date = self.parse_date(self.extract_value(69, 77), EFTError.INVALID_DEPOSIT_START_DATE)
        self.ending_deposit_date = self.parse_date(self.extract_value(89, 97), EFTError.INVALID_DEPOSIT_END_DATE)
