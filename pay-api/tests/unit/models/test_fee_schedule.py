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

"""Tests to assure the FeeSchedule Class.

Test-Suite to ensure that the FeeSchedule Class is working as expected.
"""

from datetime import date, timedelta

from pay_api.models import CorpType, FeeCode, FeeSchedule, FilingType


def factory_corp_type(corp_type_code: str, corp_description: str):
    """Return a valid Corp Type object."""
    return CorpType(code=corp_type_code,
                    description=corp_description)


def factory_feecode(fee_code: str, amount: int):
    """Return a valid FeeCode object."""
    return FeeCode(code=fee_code,
                   amount=amount)


def factory_filing_type(code: str, description: str):
    """Return a valid FilingType object."""
    return FilingType(code=code,
                      description=description)


def factory_fee_schedule(filing_type_code: str,
                         corp_type_code: str,
                         fee_code: str,
                         fee_start_date: date,
                         fee_end_date: date,
                         priority_fee_code: str = None,
                         future_effective_fee_code: str = None):
    """Return a valid FeeSchedule object."""
    return FeeSchedule(filing_type_code=filing_type_code,
                       corp_type_code=corp_type_code,
                       fee_code=fee_code,
                       fee_start_date=fee_start_date,
                       fee_end_date=fee_end_date,
                       priority_fee_code=priority_fee_code,
                       future_effective_fee_code=future_effective_fee_code)


def test_fee_schedule(session):
    """Assert a valid fee schedule is stored correctly.

    Start with a blank database.
    """
    fee_code = factory_feecode('EN000X', 100)
    corp_type = factory_corp_type('XX', 'Cooperative')
    filing_type = factory_filing_type('OTANNX', 'Annual Report')
    fee_schedule = factory_fee_schedule('OTANNX', 'XX', 'EN000X', date.today(), None)
    session.add(fee_code)
    session.add(corp_type)
    session.add(filing_type)
    session.commit()
    fee_schedule.save()

    assert fee_schedule.fee_schedule_id is not None


def test_fee_schedule_find_by_corp_type_and_filing_type(session):
    """Assert a valid fee schedule is stored correctly.

    Start with a blank database.
    """
    fee_code = factory_feecode('EN000X', 100)
    corp_type = factory_corp_type('XX', 'Cooperative')
    filing_type = factory_filing_type('OTANNX', 'Annual Report')
    fee_schedule = factory_fee_schedule('OTANNX', 'XX', 'EN000X', date.today(), None)
    session.add(fee_code)
    session.add(corp_type)
    session.add(filing_type)
    session.add(fee_schedule)
    session.commit()

    fee_schedule = fee_schedule.find_by_filing_type_and_corp_type('XX', 'OTANNX')

    assert fee_schedule.fee.amount == 100


def test_fee_schedule_find_by_corp_type_and_filing_type_invalid(session):
    """Assert a valid fee schedule is stored correctly.

    Start with a blank database.
    """
    fee_code = factory_feecode('EN000X', 100)
    corp_type = factory_corp_type('XX', 'Cooperative')
    filing_type = factory_filing_type('OTANNX', 'Annual Report')
    fee_schedule = factory_fee_schedule('OTANNX', 'XX', 'EN000X', date.today(), None)
    session.add(fee_code)
    session.add(corp_type)
    session.add(filing_type)
    session.add(fee_schedule)
    session.commit()

    fee_schedule = fee_schedule.find_by_filing_type_and_corp_type('XX', 'OTADDX')

    assert fee_schedule is None


def test_fee_schedule_find_by_corp_type_and_filing_type_valid_date(session):
    """Assert a valid fee schedule is stored correctly.

    Start with a blank database.
    """
    fee_code = factory_feecode('EN000X', 100)
    corp_type = factory_corp_type('XX', 'Cooperative')
    filing_type = factory_filing_type('OTANNX', 'Annual Report')
    fee_schedule = factory_fee_schedule('OTANNX', 'XX', 'EN000X', date.today(), None)
    session.add(fee_code)
    session.add(corp_type)
    session.add(filing_type)
    session.add(fee_schedule)
    session.commit()

    fee_schedule = fee_schedule.find_by_filing_type_and_corp_type('XX', 'OTANNX', date.today())

    assert fee_schedule.fee.amount == 100


def test_fee_schedule_find_by_corp_type_and_filing_type_invalid_date(session):
    """Assert a valid fee schedule is stored correctly.

    Start with a blank database.
    """
    now = date.today()
    fee_code = factory_feecode('EN000X', 100)
    corp_type = factory_corp_type('XX', 'Cooperative')
    filing_type = factory_filing_type('OTANNX', 'Annual Report')
    fee_schedule = factory_fee_schedule('OTANNX', 'XX', 'EN000X', now, None)
    session.add(fee_code)
    session.add(corp_type)
    session.add(filing_type)
    session.add(fee_schedule)
    session.commit()

    fee_schedule = fee_schedule.find_by_filing_type_and_corp_type('XX', 'OTANNX', date.today() - timedelta(1))

    assert fee_schedule is None


def test_fee_schedule_find_by_none_corp_type_and_filing_type(session):
    """Assert a valid fee schedule is stored correctly.

    Start with a blank database.
    """
    now = date.today()
    fee_code = factory_feecode('EN000X', 100)
    corp_type = factory_corp_type('XX', 'Cooperative')
    filing_type = factory_filing_type('OTANNX', 'Annual Report')
    fee_schedule = factory_fee_schedule('OTANNX', 'XX', 'EN000X', now, None)
    session.add(fee_code)
    session.add(corp_type)
    session.add(filing_type)
    session.add(fee_schedule)
    session.commit()

    fee_schedule = fee_schedule.find_by_filing_type_and_corp_type(None, None)

    assert fee_schedule is None
