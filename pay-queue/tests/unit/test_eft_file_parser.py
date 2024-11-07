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

"""Tests to assure the EFT File Parser.

Test-Suite to ensure that the EFT File parser is working as intended.
"""
from datetime import datetime

import pytest
from pay_api.utils.enums import EFTShortnameType

from pay_queue.services.eft import EFTHeader, EFTRecord, EFTTrailer
from pay_queue.services.eft.eft_enums import EFTConstants
from pay_queue.services.eft.eft_errors import EFTError
from tests.utilities.factory_utils import factory_eft_header, factory_eft_record, factory_eft_trailer


def test_eft_parse_header():
    """Test EFT header parser."""
    content = factory_eft_header(
        record_type=EFTConstants.HEADER_RECORD_TYPE.value,
        file_creation_date="20230814",
        file_creation_time="1601",
        deposit_start_date="20230810",
        deposit_end_date="20230810",
    )

    header: EFTHeader = EFTHeader(content, 0)

    creation_datetime = datetime(2023, 8, 14, 16, 1)
    deposit_date_start = datetime(2023, 8, 10)
    deposit_date_end = datetime(2023, 8, 10)

    assert header.index == 0
    assert header.record_type == "1"
    assert header.creation_datetime == creation_datetime
    assert header.starting_deposit_date == deposit_date_start
    assert header.ending_deposit_date == deposit_date_end


def test_eft_parse_header_invalid_length():
    """Test EFT header parser invalid length."""
    content = " "
    header: EFTHeader = EFTHeader(content, 0)

    assert header.errors
    assert len(header.errors) == 1
    assert header.errors[0].code == EFTError.INVALID_LINE_LENGTH.name
    assert header.errors[0].message == EFTError.INVALID_LINE_LENGTH.value
    assert header.errors[0].index == 0


def test_eft_parse_header_invalid_record_type():
    """Test EFT header parser invalid record type."""
    content = factory_eft_header(
        record_type="X",
        file_creation_date="20230814",
        file_creation_time="1601",
        deposit_start_date="20230810",
        deposit_end_date="20230810",
    )

    header: EFTHeader = EFTHeader(content, 0)

    assert header.errors
    assert len(header.errors) == 1
    assert header.errors[0].code == EFTError.INVALID_RECORD_TYPE.name
    assert header.errors[0].message == EFTError.INVALID_RECORD_TYPE.value
    assert header.errors[0].index == 0


def test_eft_parse_header_invalid_dates():
    """Test EFT header parser invalid dates."""
    content = factory_eft_header(
        record_type=EFTConstants.HEADER_RECORD_TYPE.value,
        file_creation_date="2023081_",
        file_creation_time="160 ",
        deposit_start_date="20230850",
        deposit_end_date="202308AB",
    )

    header: EFTHeader = EFTHeader(content, 0)

    assert header.errors
    assert len(header.errors) == 3
    assert header.errors[0].code == EFTError.INVALID_CREATION_DATETIME.name
    assert header.errors[0].message == EFTError.INVALID_CREATION_DATETIME.value
    assert header.errors[0].index == 0
    assert header.errors[1].code == EFTError.INVALID_DEPOSIT_START_DATE.name
    assert header.errors[1].message == EFTError.INVALID_DEPOSIT_START_DATE.value
    assert header.errors[1].index == 0
    assert header.errors[2].code == EFTError.INVALID_DEPOSIT_END_DATE.name
    assert header.errors[2].message == EFTError.INVALID_DEPOSIT_END_DATE.value
    assert header.errors[2].index == 0


def test_eft_parse_trailer():
    """Test EFT trailer parser."""
    content = factory_eft_trailer(
        record_type=EFTConstants.TRAILER_RECORD_TYPE.value,
        number_of_details="5",
        total_deposit_amount="3733750",
    )
    trailer: EFTTrailer = EFTTrailer(content, 1)

    assert trailer.index == 1
    assert trailer.record_type == "7"
    assert trailer.number_of_details == 5
    assert trailer.total_deposit_amount == 3733750


def test_eft_parse_trailer_invalid_length():
    """Test EFT trailer parser invalid number types."""
    content = " "
    trailer: EFTTrailer = EFTTrailer(content, 1)

    assert trailer.errors
    assert len(trailer.errors) == 1
    assert trailer.errors[0].code == EFTError.INVALID_LINE_LENGTH.name
    assert trailer.errors[0].message == EFTError.INVALID_LINE_LENGTH.value
    assert trailer.errors[0].index == 1


def test_eft_parse_trailer_invalid_record_type():
    """Test EFT trailer parser invalid record_type."""
    content = factory_eft_trailer(record_type="X", number_of_details="5", total_deposit_amount="3733750")
    trailer: EFTTrailer = EFTTrailer(content, 1)

    assert trailer.errors
    assert len(trailer.errors) == 1
    assert trailer.errors[0].code == EFTError.INVALID_RECORD_TYPE.name
    assert trailer.errors[0].message == EFTError.INVALID_RECORD_TYPE.value
    assert trailer.errors[0].index == 1


def test_eft_parse_trailer_invalid_numbers():
    """Test EFT trailer parser invalid number values."""
    content = factory_eft_trailer(
        record_type=EFTConstants.TRAILER_RECORD_TYPE.value,
        number_of_details="B",
        total_deposit_amount="3733A50",
    )
    trailer: EFTTrailer = EFTTrailer(content, 1)

    assert trailer.errors
    assert len(trailer.errors) == 2
    assert trailer.errors[0].code == EFTError.INVALID_NUMBER_OF_DETAILS.name
    assert trailer.errors[0].message == EFTError.INVALID_NUMBER_OF_DETAILS.value
    assert trailer.errors[0].index == 1
    assert trailer.errors[1].code == EFTError.INVALID_TOTAL_DEPOSIT_AMOUNT.name
    assert trailer.errors[1].message == EFTError.INVALID_TOTAL_DEPOSIT_AMOUNT.value
    assert trailer.errors[1].index == 1


@pytest.mark.parametrize(
    "test_type, short_name_type, transaction_description, line_index, expected",
    [
        (
            "EFT",
            EFTShortnameType.EFT.value,
            f"{EFTRecord.EFT_DESCRIPTION_PATTERN} EFTSN1",
            1,
            {"is_generated": False, "short_name": "EFTSN1"},
        ),
        (
            "WIRE",
            EFTShortnameType.WIRE.value,
            f"{EFTRecord.WIRE_DESCRIPTION_PATTERN} WIRESN1",
            2,
            {"is_generated": False, "short_name": "WIRESN1"},
        ),
        (
            "FEDERAL PAYMENT",
            EFTShortnameType.EFT.value,
            f"{EFTRecord.FEDERAL_PAYMENT_DESCRIPTION_PATTERN}",
            3,
            {"is_generated": True, "short_name": EFTRecord.FEDERAL_PAYMENT_DESCRIPTION_PATTERN},
        ),
        (
            "PAD",
            None,
            f"{EFTRecord.PAD_DESCRIPTION_PATTERN}",
            4,
            {"is_generated": False, "short_name": EFTRecord.PAD_DESCRIPTION_PATTERN},
        ),
        ("UNKNOWN", None, "ABC 123", 5, {"is_generated": False, "short_name": "ABC 123"}),
    ],
)
def test_eft_parse_records(test_type, short_name_type, transaction_description, line_index, expected):
    """Test EFT Record parser."""
    content = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="001",
        transaction_description=transaction_description,
        deposit_amount="13500",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="13500",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )

    record: EFTRecord = EFTRecord(content, line_index)
    deposit_datetime = datetime(2023, 8, 10, 0, 0)
    assert record.index == line_index
    assert record.record_type == "2"
    assert record.ministry_code == "AT"
    assert record.program_code == "0146"
    assert record.deposit_datetime == deposit_datetime
    assert record.location_id == "85004"
    assert record.transaction_sequence == "001"
    assert record.transaction_description == expected["short_name"]
    assert record.deposit_amount == 13500
    assert record.currency == EFTConstants.CURRENCY_CAD.value
    assert record.exchange_adj_amount == 0
    assert record.deposit_amount_cad == 13500
    assert record.dest_bank_number == "0003"
    assert record.batch_number == "002400986"
    assert record.jv_type == "I"
    assert record.jv_number == "002425669"
    assert record.short_name_type == short_name_type
    assert record.generate_short_name == expected["is_generated"]


def test_eft_parse_record_invalid_length():
    """Test EFT record parser invalid length."""
    content = " "
    record: EFTRecord = EFTRecord(content, 0)

    assert record.errors
    assert len(record.errors) == 1
    assert record.errors[0].code == EFTError.INVALID_LINE_LENGTH.name
    assert record.errors[0].message == EFTError.INVALID_LINE_LENGTH.value
    assert record.errors[0].index == 0


def test_eft_parse_record_invalid_record_type():
    """Test EFT record parser invalid record_type."""
    content = factory_eft_record(
        record_type="X",
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="001",
        transaction_description="DEPOSIT          26",
        deposit_amount="13500",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="13500",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )
    record: EFTRecord = EFTRecord(content, 0)

    assert record.errors
    assert len(record.errors) == 1
    assert record.errors[0].code == EFTError.INVALID_RECORD_TYPE.name
    assert record.errors[0].message == EFTError.INVALID_RECORD_TYPE.value
    assert record.errors[0].index == 0


def test_eft_parse_record_invalid_dates():
    """Test EFT record parser for invalid dates."""
    content = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="2023081 ",
        deposit_time="A000",
        location_id="85004",
        transaction_sequence="001",
        transaction_description="DEPOSIT          26",
        deposit_amount="13500",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="13500",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="20233001",
    )
    record: EFTRecord = EFTRecord(content, 1)

    assert record.errors
    assert len(record.errors) == 2
    assert record.errors[0].code == EFTError.INVALID_DEPOSIT_DATETIME.name
    assert record.errors[0].message == EFTError.INVALID_DEPOSIT_DATETIME.value
    assert record.errors[0].index == 1
    assert record.errors[1].code == EFTError.INVALID_TRANSACTION_DATE.name
    assert record.errors[1].message == EFTError.INVALID_TRANSACTION_DATE.value
    assert record.errors[1].index == 1

    assert record.index == 1
    assert record.record_type == "2"
    assert record.ministry_code == "AT"
    assert record.program_code == "0146"
    assert record.deposit_datetime is None
    assert record.location_id == "85004"
    assert record.transaction_sequence == "001"
    assert record.transaction_description == "DEPOSIT          26"
    assert record.deposit_amount == 13500
    assert record.currency == EFTConstants.CURRENCY_CAD.value
    assert record.exchange_adj_amount == 0
    assert record.deposit_amount_cad == 13500
    assert record.dest_bank_number == "0003"
    assert record.batch_number == "002400986"
    assert record.jv_type == "I"
    assert record.jv_number == "002425669"
    assert record.transaction_date is None


def test_eft_parse_record_invalid_numbers():
    """Test EFT record parser for invalid numbers."""
    content = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="001",
        transaction_description="1234",
        deposit_amount="1350A",
        currency="",
        exchange_adj_amount="ABC",
        deposit_amount_cad="1350A",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )
    record: EFTRecord = EFTRecord(content, 0)

    # We are expecting the transaction description as this is where we get the BCROS Account number
    assert record.errors
    assert len(record.errors) == 3
    assert record.errors[0].code == EFTError.INVALID_DEPOSIT_AMOUNT.name
    assert record.errors[0].message == EFTError.INVALID_DEPOSIT_AMOUNT.value
    assert record.errors[0].index == 0
    assert record.errors[1].code == EFTError.INVALID_EXCHANGE_ADJ_AMOUNT.name
    assert record.errors[1].message == EFTError.INVALID_EXCHANGE_ADJ_AMOUNT.value
    assert record.errors[1].index == 0
    assert record.errors[2].code == EFTError.INVALID_DEPOSIT_AMOUNT_CAD.name
    assert record.errors[2].message == EFTError.INVALID_DEPOSIT_AMOUNT_CAD.value
    assert record.errors[2].index == 0


def test_eft_parse_record_transaction_description_required():
    """Test EFT record parser transaction description required."""
    content = factory_eft_record(
        record_type=EFTConstants.TRANSACTION_RECORD_TYPE.value,
        ministry_code="AT",
        program_code="0146",
        deposit_date="20230810",
        deposit_time="0000",
        location_id="85004",
        transaction_sequence="001",
        transaction_description="",
        deposit_amount="13500",
        currency="",
        exchange_adj_amount="0",
        deposit_amount_cad="13500",
        destination_bank_number="0003",
        batch_number="002400986",
        jv_type="I",
        jv_number="002425669",
        transaction_date="",
    )
    record: EFTRecord = EFTRecord(content, 0)

    # We are expecting the transaction description as this is where we get the BCROS Account number
    assert record.errors
    assert len(record.errors) == 1
    assert record.errors[0].code == EFTError.ACCOUNT_SHORTNAME_REQUIRED.name
    assert record.errors[0].message == EFTError.ACCOUNT_SHORTNAME_REQUIRED.value
    assert record.errors[0].index == 0


def test_eft_parse_file():
    """Test EFT parsing a file."""
    with open("tests/unit/test_data/tdi17_sample.txt", "r") as f:
        contents = f.read()
        lines = contents.splitlines()
        header_index = 0
        trailer_index = len(lines) - 1
        eft_records: [EFTRecord] = []

        eft_header = EFTHeader(lines[header_index], header_index)
        eft_trailer = EFTTrailer(lines[trailer_index], trailer_index)

        for i in range(1, len(lines) - 1):
            eft_records.append(EFTRecord(lines[i], i))

        assert eft_header is not None
        assert eft_trailer is not None
        assert len(eft_records) == 6

        assert eft_header.index == 0
        assert eft_header.record_type == "1"
        assert eft_header.creation_datetime == datetime(2023, 8, 14, 16, 1)
        assert eft_header.starting_deposit_date == datetime(2023, 8, 10)
        assert eft_header.ending_deposit_date == datetime(2023, 8, 10)

        assert eft_trailer.index == 7
        assert eft_trailer.record_type == "7"
        assert eft_trailer.number_of_details == 6
        assert eft_trailer.total_deposit_amount == 3733750

        assert eft_records[0].index == 1
        assert eft_records[0].record_type == "2"
        assert eft_records[0].ministry_code == "AT"
        assert eft_records[0].program_code == "0146"
        assert eft_records[0].deposit_datetime == datetime(2023, 8, 10, 0, 0)
        assert eft_records[0].location_id == "85004"
        assert eft_records[0].transaction_sequence == "001"
        assert eft_records[0].transaction_description == "DEPOSIT          26"
        assert eft_records[0].deposit_amount == 13500
        assert eft_records[0].currency == EFTConstants.CURRENCY_CAD.value
        assert eft_records[0].exchange_adj_amount == 0
        assert eft_records[0].deposit_amount_cad == 13500
        assert eft_records[0].dest_bank_number == "0003"
        assert eft_records[0].batch_number == "002400986"
        assert eft_records[0].jv_type == "I"
        assert eft_records[0].jv_number == "002425669"
        assert eft_records[0].transaction_date is None
        assert eft_records[0].short_name_type is None

        assert eft_records[1].index == 2
        assert eft_records[1].record_type == "2"
        assert eft_records[1].ministry_code == "AT"
        assert eft_records[1].program_code == "0146"
        assert eft_records[1].deposit_datetime == datetime(2023, 8, 10, 0, 0)
        assert eft_records[1].location_id == "85004"
        assert eft_records[1].transaction_sequence == "002"
        assert eft_records[1].transaction_description == "HSIMPSON"
        assert eft_records[1].deposit_amount == 525000
        assert eft_records[1].currency == EFTConstants.CURRENCY_CAD.value
        assert eft_records[1].exchange_adj_amount == 0
        assert eft_records[1].deposit_amount_cad == 525000
        assert eft_records[1].dest_bank_number == "0003"
        assert eft_records[1].batch_number == "002400986"
        assert eft_records[1].jv_type == "I"
        assert eft_records[1].jv_number == "002425669"
        assert eft_records[1].transaction_date is None
        assert eft_records[1].short_name_type == EFTShortnameType.WIRE.value

        assert eft_records[2].index == 3
        assert eft_records[2].record_type == "2"
        assert eft_records[2].ministry_code == "AT"
        assert eft_records[2].program_code == "0146"
        assert eft_records[2].deposit_datetime == datetime(2023, 8, 10, 0, 0)
        assert eft_records[2].location_id == "85004"
        assert eft_records[2].transaction_sequence == "003"
        assert eft_records[2].transaction_description == "ABC1234567"
        assert eft_records[2].deposit_amount == 951250
        assert eft_records[2].currency == EFTConstants.CURRENCY_CAD.value
        assert eft_records[2].exchange_adj_amount == 0
        assert eft_records[2].deposit_amount_cad == 951250
        assert eft_records[2].dest_bank_number == "0003"
        assert eft_records[2].batch_number == "002400986"
        assert eft_records[2].jv_type == "I"
        assert eft_records[2].jv_number == "002425669"
        assert eft_records[2].transaction_date is None
        assert eft_records[2].short_name_type == EFTShortnameType.EFT.value

        assert eft_records[3].index == 4
        assert eft_records[3].record_type == "2"
        assert eft_records[3].ministry_code == "AT"
        assert eft_records[3].program_code == "0146"
        assert eft_records[3].deposit_datetime == datetime(2023, 8, 10, 0, 0)
        assert eft_records[3].location_id == "85004"
        assert eft_records[3].transaction_sequence == "004"
        assert eft_records[3].transaction_description == "INTERBLOCK C"
        assert eft_records[3].deposit_amount == 2125000
        assert eft_records[3].currency == EFTConstants.CURRENCY_CAD.value
        assert eft_records[3].exchange_adj_amount == 0
        assert eft_records[3].deposit_amount_cad == 2125000
        assert eft_records[3].dest_bank_number == "0003"
        assert eft_records[3].batch_number == "002400986"
        assert eft_records[3].jv_type == "I"
        assert eft_records[3].jv_number == "002425669"
        assert eft_records[3].transaction_date is None
        assert eft_records[3].short_name_type == EFTShortnameType.WIRE.value

        assert eft_records[4].index == 5
        assert eft_records[4].record_type == "2"
        assert eft_records[4].ministry_code == "AT"
        assert eft_records[4].program_code == "0146"
        assert eft_records[4].deposit_datetime == datetime(2023, 8, 10, 16, 0)
        assert eft_records[4].location_id == "85020"
        assert eft_records[4].transaction_sequence == "001"
        assert eft_records[4].transaction_description == ""
        assert eft_records[4].deposit_amount == 119000
        assert eft_records[4].currency == EFTConstants.CURRENCY_CAD.value
        assert eft_records[4].exchange_adj_amount == 0
        assert eft_records[4].deposit_amount_cad == 119000
        assert eft_records[4].dest_bank_number == "0010"
        assert eft_records[4].batch_number == "002400989"
        assert eft_records[4].jv_type == "I"
        assert eft_records[4].jv_number == "002425836"
        assert eft_records[4].transaction_date is None
        assert eft_records[4].short_name_type is None

        assert eft_records[5].index == 6
        assert eft_records[5].record_type == "2"
        assert eft_records[5].ministry_code == "AT"
        assert eft_records[5].program_code == "0146"
        assert eft_records[5].deposit_datetime == datetime(2023, 8, 10, 16, 0)
        assert eft_records[5].location_id == "85020"
        assert eft_records[5].transaction_sequence == "001"
        assert eft_records[5].transaction_description == "FEDERAL PAYMENT CANADA"
        assert eft_records[5].deposit_amount == 119000
        assert eft_records[5].currency == EFTConstants.CURRENCY_CAD.value
        assert eft_records[5].exchange_adj_amount == 0
        assert eft_records[5].deposit_amount_cad == 119000
        assert eft_records[5].dest_bank_number == "0010"
        assert eft_records[5].batch_number == "002400989"
        assert eft_records[5].jv_type == "I"
        assert eft_records[5].jv_number == "002425836"
        assert eft_records[5].transaction_date is None
        assert eft_records[5].short_name_type == EFTShortnameType.EFT.value
        assert eft_records[5].generate_short_name is True
