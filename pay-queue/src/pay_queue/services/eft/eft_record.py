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
"""This manages the EFT Transaction record."""
import decimal
from datetime import datetime
from typing import Tuple

from pay_api.utils.enums import EFTShortnameType

from pay_queue.services.eft.eft_base import EFTBase
from pay_queue.services.eft.eft_enums import EFTConstants
from pay_queue.services.eft.eft_errors import EFTError
from pay_queue.services.eft.eft_parse_error import EFTParseError


class EFTRecord(EFTBase):
    """Defines the structure of the transaction record of a received EFT file."""

    PAD_DESCRIPTION_PATTERN = "MISC PAYMENT BCONLINE"
    EFT_DESCRIPTION_PATTERN = "MISC PAYMENT"
    WIRE_DESCRIPTION_PATTERN = "FUNDS TRANSFER CR TT"
    FEDERAL_PAYMENT_DESCRIPTION_PATTERN = "FEDERAL PAYMENT CANADA"
    GENERATE_SHORT_NAME_PATTERNS: Tuple = (FEDERAL_PAYMENT_DESCRIPTION_PATTERN, )

    ministry_code: str
    program_code: str
    location_id: str
    deposit_datetime: datetime
    transaction_sequence: str  # optional
    transaction_description: str = None
    deposit_amount: decimal
    currency: str  # blank = CAD, US = USD
    exchange_adj_amount: decimal  # in cents
    deposit_amount_cad: decimal  # Deposit amount in CAD, in cents
    dest_bank_number: str
    batch_number: str  # optional; specified only if posted to GL
    jv_type: str  # I = inter, J = intra; mandatory if JV batch specified
    jv_number: str  # mandatory if JV batch specified
    transaction_date: datetime  # optional
    short_name_type: str = None
    generate_short_name: bool = False

    def __init__(self, content: str, index: int):
        """Return an EFT Transaction record."""
        super().__init__(content, index)
        self._process()

    @staticmethod
    def get_currency(currency: str) -> str:
        """Get the appropriate exchange currency."""
        if len(currency.strip()) == 0:  # Blank currency means CAD
            return EFTConstants.CURRENCY_CAD.value

        return currency

    def _process(self):
        """Process and validate EFT Transaction record string."""
        # Confirm line length is valid, skip if it is not, but add to error array
        if not self.is_valid_length():
            self.add_error(EFTParseError(EFTError.INVALID_LINE_LENGTH))
            return

        # Confirm record type is as expected
        self.record_type = self.extract_value(0, 1)
        self.validate_record_type(EFTConstants.TRANSACTION_RECORD_TYPE.value)

        self.ministry_code = self.extract_value(1, 3)
        self.program_code = self.extract_value(3, 7)

        deposit_time = self.extract_value(20, 24)
        deposit_time = "0000" if len(deposit_time) == 0 else deposit_time  # default to 0000 if time not provided

        self.deposit_datetime = self.parse_datetime(
            self.extract_value(7, 15) + deposit_time, EFTError.INVALID_DEPOSIT_DATETIME
        )
        self.location_id = self.extract_value(15, 20)
        self.transaction_sequence = self.extract_value(24, 27)

        # We are expecting a SHORTNAME for matching here, it is required
        self.transaction_description = self.extract_value(27, 67)
        if len(self.transaction_description) == 0:
            self.add_error(EFTParseError(EFTError.ACCOUNT_SHORTNAME_REQUIRED))
        self.parse_transaction_description()

        self.deposit_amount = self.parse_decimal(self.extract_value(67, 80), EFTError.INVALID_DEPOSIT_AMOUNT)
        self.currency = self.get_currency(self.extract_value(80, 82))
        self.exchange_adj_amount = self.parse_decimal(self.extract_value(82, 95), EFTError.INVALID_EXCHANGE_ADJ_AMOUNT)
        self.deposit_amount_cad = self.parse_decimal(self.extract_value(95, 108), EFTError.INVALID_DEPOSIT_AMOUNT_CAD)
        self.dest_bank_number = self.extract_value(108, 112)
        self.batch_number = self.extract_value(112, 121)
        self.jv_type = self.extract_value(121, 122)
        self.jv_number = self.extract_value(122, 131)

        # transaction date is optional - parse if there is a value
        transaction_date = self.extract_value(131, 139)
        self.transaction_date = (
            None if len(transaction_date) == 0 else self.parse_date(transaction_date, EFTError.INVALID_TRANSACTION_DATE)
        )

    def parse_transaction_description(self):
        """Determine if the transaction is an EFT/Wire and parse it."""
        if not self.transaction_description:
            return

        if self.transaction_description.startswith(self.GENERATE_SHORT_NAME_PATTERNS):
            self.short_name_type = EFTShortnameType.EFT.value
            self.transaction_description = self.FEDERAL_PAYMENT_DESCRIPTION_PATTERN.strip()
            self.generate_short_name = True
            return

        if self.transaction_description.startswith(self.WIRE_DESCRIPTION_PATTERN):
            self.short_name_type = EFTShortnameType.WIRE.value
            self.transaction_description = self.transaction_description[len(self.WIRE_DESCRIPTION_PATTERN) :].strip()
            return

        # Check if this a PAD or EFT Transaction
        if self.transaction_description.startswith(
            self.EFT_DESCRIPTION_PATTERN
        ) and not self.transaction_description.startswith(self.PAD_DESCRIPTION_PATTERN):
            self.short_name_type = EFTShortnameType.EFT.value
            self.transaction_description = self.transaction_description[len(self.EFT_DESCRIPTION_PATTERN) :].strip()
