# Copyright © 2019 Province of British Columbia
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

from datetime import date, timedelta

import pytest

from pay_api import services
from pay_api.models import CorpType, FeeCode, FilingType
from pay_api.utils.errors import Error


CORP_TYPE_CODE = 'CPX'
FILING_TYPE_CODE = 'OTANNX'

FEE_CODE = 'EN101X'


def test_fee_schedule_saved_from_new(session):
    """Assert that the fee schedule is saved to the table."""
    create_linked_data(FILING_TYPE_CODE, CORP_TYPE_CODE, FEE_CODE)
    fee_schedule = services.FeeSchedule()
    fee_schedule.filing_type_code = FILING_TYPE_CODE
    fee_schedule.corp_type_code = CORP_TYPE_CODE
    fee_schedule.fee_code = FEE_CODE
    fee_schedule.fee_start_date = date.today()
    fee_schedule.save()

    fee_schedule = services.FeeSchedule.find_by_corp_type_and_filing_type(CORP_TYPE_CODE, FILING_TYPE_CODE,
                                                                          None, None, None)

    assert fee_schedule is not None


def test_find_by_corp_type_and_filing_type_from_new(session):
    """Assert that the fee schedule is saved to the table."""
    create_linked_data(FILING_TYPE_CODE, CORP_TYPE_CODE, FEE_CODE)
    fee_schedule = services.FeeSchedule()
    fee_schedule.filing_type_code = FILING_TYPE_CODE
    fee_schedule.corp_type_code = CORP_TYPE_CODE
    fee_schedule.fee_code = FEE_CODE
    fee_schedule.fee_start_date = date.today()
    fee_schedule.save()

    fee_schedule = services.FeeSchedule.find_by_corp_type_and_filing_type(CORP_TYPE_CODE, FILING_TYPE_CODE,
                                                                          None, None, None)

    assert fee_schedule.fee_schedule_id is not None
    assert fee_schedule.fee_start_date == date.today()
    assert fee_schedule.fee_end_date is None
    assert fee_schedule.fee_code == FEE_CODE
    assert fee_schedule.corp_type_code == CORP_TYPE_CODE
    assert fee_schedule.filing_type_code == FILING_TYPE_CODE

    assert fee_schedule.asdict() == {
        'filing_type': 'TEST',
        'filing_type_code': FILING_TYPE_CODE,
        'filing_fees': 100,
        'service_fees': 0,
        'processing_fees': 0,
        'tax':
            {
                'gst': 0,
                'pst': 0
            }
    }


def test_find_by_corp_type_and_filing_type_from_none(session):
    """Assert that the fee schedule is saved to the table."""
    from pay_api.exceptions import BusinessException

    with pytest.raises(BusinessException) as excinfo:
        services.FeeSchedule.find_by_corp_type_and_filing_type(None, None, None, None, None)
    assert excinfo.value.status == Error.PAY001.status
    assert excinfo.value.message == Error.PAY001.message
    assert excinfo.value.code == Error.PAY001.name


def test_find_by_corp_type_and_filing_type_invalid(session):
    """Assert that the fee schedule is saved to the table."""
    from pay_api.exceptions import BusinessException

    with pytest.raises(BusinessException) as excinfo:
        services.FeeSchedule.find_by_corp_type_and_filing_type('XX', 'XXXX', None, None, None)
    assert excinfo.value.status == Error.PAY002.status
    assert excinfo.value.message == Error.PAY002.message
    assert excinfo.value.code == Error.PAY002.name


def test_find_by_corp_type_and_filing_type_and_valid_date(session):
    """Assert that the fee schedule is saved to the table."""
    create_linked_data(FILING_TYPE_CODE, CORP_TYPE_CODE, FEE_CODE)
    fee_schedule = services.FeeSchedule()
    fee_schedule.filing_type_code = FILING_TYPE_CODE
    fee_schedule.corp_type_code = CORP_TYPE_CODE
    fee_schedule.fee_code = FEE_CODE
    fee_schedule.fee_start_date = date.today()
    fee_schedule.save()

    fee_schedule = services.FeeSchedule.find_by_corp_type_and_filing_type(CORP_TYPE_CODE, FILING_TYPE_CODE,
                                                                          date.today(), None, None)

    assert fee_schedule.fee_schedule_id is not None


def test_find_by_corp_type_and_filing_type_and_invalid_date(session):
    """Assert that the fee schedule is saved to the table."""
    from pay_api.exceptions import BusinessException
    create_linked_data(FILING_TYPE_CODE, CORP_TYPE_CODE, FEE_CODE)
    fee_schedule = services.FeeSchedule()
    fee_schedule.filing_type_code = FILING_TYPE_CODE
    fee_schedule.corp_type_code = CORP_TYPE_CODE
    fee_schedule.fee_code = FEE_CODE
    fee_schedule.fee_start_date = date.today()
    fee_schedule.save()

    with pytest.raises(BusinessException) as excinfo:
        fee_schedule = services.FeeSchedule.find_by_corp_type_and_filing_type(CORP_TYPE_CODE, FILING_TYPE_CODE,
                                                                              date.today() - timedelta(1), None, None)

    assert excinfo.value.status == Error.PAY002.status


def create_linked_data(
        filing_type_code: str,
        corp_type_code: str,
        fee_code: str):
    """Return a valid fee schedule object, creates the related objects first."""
    corp_type = CorpType(corp_type_code=corp_type_code,
                         corp_type_description='TEST')
    corp_type.save()

    fee_code_master = FeeCode(fee_code=fee_code,
                              amount=100)
    fee_code_master.save()

    filing_type = FilingType(filing_type_code=filing_type_code,
                             filing_description='TEST')
    filing_type.save()
