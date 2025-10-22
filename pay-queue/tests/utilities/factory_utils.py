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
"""Test Utils.

Test Factory Utility for creating test data.
"""

from pay_queue.services.eft.eft_enums import EFTConstants


def factory_eft_header(
    record_type: str,
    file_creation_date: str,
    file_creation_time: str,
    deposit_start_date: str,
    deposit_end_date,
) -> str:
    """Produce eft header TDI17 formatted string."""
    result = (
        f"{record_type}CREATION DATE: {file_creation_date}CREATION TIME:   {file_creation_time}"
        f"DEPOSIT DATE(S) FROM:   {deposit_start_date} TO DATE :  {deposit_end_date}"
    )
    result = eft_pad_line_length(result)  # Pad end of line length

    return result


def factory_eft_trailer(record_type: str, number_of_details: str, total_deposit_amount: str) -> str:
    """Produce eft trailer TDI17 formatted string."""
    total_deposit_amount = transform_money_string(total_deposit_amount)
    result = f"{record_type}{left_pad_zero(number_of_details, 6)}{left_pad_zero(total_deposit_amount, 14)}"
    result = eft_pad_line_length(result)

    return result


def factory_eft_record(
    record_type: str,
    ministry_code: str,
    program_code: str,
    deposit_date: str,
    deposit_time: str,
    location_id: str,
    transaction_sequence: str,
    transaction_description: str,
    deposit_amount: str,
    currency: str,
    exchange_adj_amount: str,
    deposit_amount_cad: str,
    destination_bank_number: str,
    batch_number: str,
    jv_type: str,
    jv_number: str,
    transaction_date: str,
) -> str:
    """Produce eft transaction record TDI17 formatted string."""
    deposit_amount = transform_money_string(deposit_amount)
    exchange_adj_amount = transform_money_string(exchange_adj_amount)
    deposit_amount_cad = transform_money_string(deposit_amount_cad)

    result = (
        f"{record_type}{ministry_code}{program_code}{deposit_date}{location_id}"
        f"{right_pad_space(deposit_time, 4)}"
        f"{transaction_sequence}{right_pad_space(transaction_description, 40)}"
        f"{left_pad_zero(deposit_amount, 13)}{right_pad_space(currency, 2)}"
        f"{left_pad_zero(exchange_adj_amount, 13)}{left_pad_zero(deposit_amount_cad, 13)}"
        f"{destination_bank_number}{batch_number}{jv_type}{jv_number}{transaction_date}"
    )
    result = eft_pad_line_length(result)

    return result


def transform_money_string(money_str: str) -> str:
    """Produce a properly formatted string for TDI17 money values."""
    money_str = money_str.strip()

    if not money_str.endswith("-"):  # Ends with minus sign if it is a negative value
        money_str = money_str + " "  # Add a blank for positive value

    return money_str


def left_pad_zero(value: str, width: int) -> str:
    """Produce left padded zero string."""
    return "{:0>{}}".format(value, width)


def right_pad_space(value: str, width: int) -> str:
    """Produce end padded white spaced string."""
    return "{:<{}}".format(value, width)  # Pad end of line length


def eft_pad_line_length(value: str) -> str:
    """Produce end padded white spaced string for an EFT record."""
    return right_pad_space(value, EFTConstants.EXPECTED_LINE_LENGTH.value)
