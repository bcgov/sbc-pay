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

"""Tests to assure the FeeSchedule Service.

Test-Suite to ensure that the FeeSchedule Service is working as expected.
"""

from datetime import datetime, timedelta, timezone

import pytest

from pay_api import services
from pay_api.models import CorpType, FeeCode
from pay_api.models import FeeSchedule as FeesScheduleModel
from pay_api.models import FilingType
from pay_api.utils.errors import Error


CORP_TYPE_CODE = "CPX"
FILING_TYPE_CODE = "OTANNX"

FEE_CODE = "EN101X"


def test_fee_schedule_saved_from_new(session):
    """Assert that the fee schedule is saved to the table."""
    create_linked_data(FILING_TYPE_CODE, CORP_TYPE_CODE, FEE_CODE)
    fee_schedule = services.FeeSchedule()
    fee_schedule.filing_type_code = FILING_TYPE_CODE
    fee_schedule.corp_type_code = CORP_TYPE_CODE
    fee_schedule.fee_code = FEE_CODE
    fee_schedule.fee_start_date = datetime.now(tz=timezone.utc)
    fee_schedule.save()

    fee_schedule = services.FeeSchedule.find_by_corp_type_and_filing_type(CORP_TYPE_CODE, FILING_TYPE_CODE, None)

    assert fee_schedule is not None


def test_find_by_corp_type_and_filing_type_from_new(session):
    """Assert that the fee schedule is saved to the table."""
    create_linked_data(FILING_TYPE_CODE, CORP_TYPE_CODE, FEE_CODE)
    fee_schedule = services.FeeSchedule()
    fee_schedule.filing_type_code = FILING_TYPE_CODE
    fee_schedule.corp_type_code = CORP_TYPE_CODE
    fee_schedule.fee_code = FEE_CODE
    fee_schedule.fee_start_date = datetime.now(tz=timezone.utc)
    fee_schedule.save()

    fee_schedule = services.FeeSchedule.find_by_corp_type_and_filing_type(CORP_TYPE_CODE, FILING_TYPE_CODE, None)

    assert fee_schedule.fee_schedule_id is not None
    assert fee_schedule.fee_start_date == datetime.now(tz=timezone.utc).date()
    assert fee_schedule.fee_end_date is None
    assert fee_schedule.fee_code == FEE_CODE
    assert fee_schedule.corp_type_code == CORP_TYPE_CODE
    assert fee_schedule.filing_type_code == FILING_TYPE_CODE

    assert fee_schedule.asdict() == {
        "filing_type": "TEST",
        "filing_type_code": FILING_TYPE_CODE,
        "filing_fees": 100,
        "service_fees": 0,
        "total": 100,
        "tax": {"gst": 0, "pst": 0},
        "priority_fees": 0,
        "future_effective_fees": 0,
        "processing_fees": 0,
    }


def test_find_by_corp_type_and_filing_type_from_none(session):
    """Assert that the fee schedule is saved to the table."""
    from pay_api.exceptions import BusinessException

    with pytest.raises(BusinessException) as excinfo:
        services.FeeSchedule.find_by_corp_type_and_filing_type(None, None, None)
    assert excinfo.value.code == Error.INVALID_CORP_OR_FILING_TYPE.name


def test_find_by_corp_type_and_filing_type_invalid(session):
    """Assert that the fee schedule is saved to the table."""
    from pay_api.exceptions import BusinessException

    with pytest.raises(BusinessException) as excinfo:
        services.FeeSchedule.find_by_corp_type_and_filing_type("XX", "XXXX", None)
    assert excinfo.value.code == Error.INVALID_CORP_OR_FILING_TYPE.name


def test_find_by_corp_type_and_filing_type_and_valid_date(session):
    """Assert that the fee schedule is saved to the table."""
    create_linked_data(FILING_TYPE_CODE, CORP_TYPE_CODE, FEE_CODE)
    fee_schedule = services.FeeSchedule()
    fee_schedule.filing_type_code = FILING_TYPE_CODE
    fee_schedule.corp_type_code = CORP_TYPE_CODE
    fee_schedule.fee_code = FEE_CODE
    fee_schedule.fee_start_date = datetime.now(tz=timezone.utc)
    fee_schedule.save()

    fee_schedule = services.FeeSchedule.find_by_corp_type_and_filing_type(
        CORP_TYPE_CODE, FILING_TYPE_CODE, datetime.now(tz=timezone.utc)
    )

    assert fee_schedule.fee_schedule_id is not None


def test_find_by_corp_type_and_filing_type_and_invalid_date(session):
    """Assert that the fee schedule is saved to the table."""
    from pay_api.exceptions import BusinessException

    create_linked_data(FILING_TYPE_CODE, CORP_TYPE_CODE, FEE_CODE)
    fee_schedule = services.FeeSchedule()
    fee_schedule.filing_type_code = FILING_TYPE_CODE
    fee_schedule.corp_type_code = CORP_TYPE_CODE
    fee_schedule.fee_code = FEE_CODE
    fee_schedule.fee_start_date = datetime.now(tz=timezone.utc)
    fee_schedule.save()

    with pytest.raises(BusinessException) as excinfo:
        fee_schedule = services.FeeSchedule.find_by_corp_type_and_filing_type(
            CORP_TYPE_CODE,
            FILING_TYPE_CODE,
            datetime.now(tz=timezone.utc) - timedelta(1),
        )

    assert excinfo.value.code == Error.INVALID_CORP_OR_FILING_TYPE.name


def test_fee_schedule_with_priority_and_future_effective_filing_rates(session):
    """Assert that the fee schedule is saved to the table."""
    create_linked_data(
        FILING_TYPE_CODE,
        CORP_TYPE_CODE,
        FEE_CODE,
        priority_fee="PR001",
        future_effective_fee="FU001",
    )
    FeesScheduleModel(
        filing_type_code=FILING_TYPE_CODE,
        corp_type_code=CORP_TYPE_CODE,
        fee_code=FEE_CODE,
        future_effective_fee_code="FU001",
        priority_fee_code="PR001",
    ).save()

    fee_schedule = services.FeeSchedule.find_by_corp_type_and_filing_type(
        CORP_TYPE_CODE,
        FILING_TYPE_CODE,
        None,
        is_priority=True,
        is_future_effective=True,
    )

    assert fee_schedule is not None


def test_fee_schedule_with_waive_fees(session):
    """Assert that the fee schedule is saved to the table."""
    create_linked_data(FILING_TYPE_CODE, CORP_TYPE_CODE, FEE_CODE)
    fee_schedule = services.FeeSchedule()
    fee_schedule.filing_type_code = FILING_TYPE_CODE
    fee_schedule.corp_type_code = CORP_TYPE_CODE
    fee_schedule.fee_code = FEE_CODE
    fee_schedule.fee_start_date = datetime.now(tz=timezone.utc)
    fee_schedule.save()

    fee_schedule = services.FeeSchedule.find_by_corp_type_and_filing_type(
        CORP_TYPE_CODE, FILING_TYPE_CODE, datetime.now(tz=timezone.utc), waive_fees=True
    )

    assert fee_schedule is not None
    assert fee_schedule.fee_amount == 0


def test_fee_schedule_with_service_fees(session):
    """Assert that fee with service fees can be retrieved."""
    # Create a transaction fee
    tran_fee_code = "TRAN"
    corp_type_code = "XCORP"
    fee_code = "FEE01"
    fee_code_master = FeeCode(code=tran_fee_code, amount=10)
    fee_code_master.save()

    fee_code_master = FeeCode(code=fee_code, amount=100)
    fee_code_master.save()

    corp_type = CorpType(code=corp_type_code, description="TEST")
    corp_type.save()

    filing_type = FilingType(code=FILING_TYPE_CODE, description="TEST")
    filing_type.save()

    fee_schedule = services.FeeSchedule()
    fee_schedule.filing_type_code = FILING_TYPE_CODE
    fee_schedule.corp_type_code = corp_type_code
    fee_schedule.fee_code = fee_code
    fee_schedule.fee_start_date = datetime.now(tz=timezone.utc)
    fee_schedule.service_fee_code = tran_fee_code
    fee_schedule.save()

    fee_schedule = services.FeeSchedule.find_by_corp_type_and_filing_type(
        corp_type=corp_type_code,
        filing_type_code=FILING_TYPE_CODE,
        valid_date=datetime.now(tz=timezone.utc),
        include_service_fees=True,
    )
    assert fee_schedule.service_fees == 10


def test_fee_schedule_with_service_fees_for_basic_user(session):
    """Assert that fee with service fees can be retrieved."""
    # Create a transaction fee
    tran_fee_code = "TRAN"
    corp_type_code = "XCORP"
    fee_code = "FEE01"
    fee_code_master = FeeCode(code=tran_fee_code, amount=10)
    fee_code_master.save()

    fee_code_master = FeeCode(code=fee_code, amount=100)
    fee_code_master.save()

    corp_type = CorpType(code=corp_type_code, description="TEST")
    corp_type.save()

    filing_type = FilingType(code=FILING_TYPE_CODE, description="TEST")
    filing_type.save()

    fee_schedule = services.FeeSchedule()
    fee_schedule.filing_type_code = FILING_TYPE_CODE
    fee_schedule.corp_type_code = corp_type_code
    fee_schedule.fee_code = fee_code
    fee_schedule.fee_start_date = datetime.now(tz=timezone.utc)
    fee_schedule.service_fee_code = tran_fee_code
    fee_schedule.save()

    fee_schedule = services.FeeSchedule.find_by_corp_type_and_filing_type(
        corp_type=corp_type_code,
        filing_type_code=FILING_TYPE_CODE,
        valid_date=datetime.now(tz=timezone.utc),
        include_service_fees=False,
    )
    assert fee_schedule.service_fees == 10


def create_linked_data(
    filing_type_code: str,
    corp_type_code: str,
    fee_code: str,
    priority_fee: str = None,
    future_effective_fee: str = None,
):
    """Return a valid fee schedule object, creates the related objects first."""
    corp_type = CorpType(code=corp_type_code, description="TEST")
    corp_type.save()

    fee_code_master = FeeCode(code=fee_code, amount=100)
    fee_code_master.save()

    if priority_fee:
        priority_fee_code = FeeCode(code=priority_fee, amount=10)
        priority_fee_code.save()
    if future_effective_fee:
        future_effective_fee_code = FeeCode(code=future_effective_fee, amount=20)
        future_effective_fee_code.save()

    filing_type = FilingType(code=filing_type_code, description="TEST")
    filing_type.save()
