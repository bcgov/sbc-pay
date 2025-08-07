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

"""Tests to assure the FeeSchedule Class.

Test-Suite to ensure that the FeeSchedule Class is working as expected.
"""

from datetime import date, datetime, timedelta, timezone

from pay_api.models import CorpType, FeeCode, FeeSchedule, FilingType


def factory_corp_type(corp_type_code: str, corp_description: str):
    """Return a valid Corp Type object."""
    return CorpType(code=corp_type_code, description=corp_description)


def factory_feecode(fee_code: str, amount: int):
    """Return a valid FeeCode object."""
    return FeeCode(code=fee_code, amount=amount)


def factory_filing_type(code: str, description: str):
    """Return a valid FilingType object."""
    return FilingType(code=code, description=description)


def factory_fee_schedule(
    filing_type_code: str,
    corp_type_code: str,
    fee_code: str,
    fee_start_date: date,
    fee_end_date: date,
    priority_fee_code: str = None,
    future_effective_fee_code: str = None,
    service_fee_code: str = None,
    show_on_pricelist: bool = True,
):
    """Return a valid FeeSchedule object."""
    return FeeSchedule(
        filing_type_code=filing_type_code,
        corp_type_code=corp_type_code,
        fee_code=fee_code,
        fee_start_date=fee_start_date,
        fee_end_date=fee_end_date,
        priority_fee_code=priority_fee_code,
        future_effective_fee_code=future_effective_fee_code,
        service_fee_code=service_fee_code,
        show_on_pricelist=show_on_pricelist,
    )


def test_fee_schedule(session):
    """Assert a valid fee schedule is stored correctly.

    Start with a blank database.
    """
    fee_code = factory_feecode("EN000X", 100)
    corp_type = factory_corp_type("XX", "Cooperative")
    filing_type = factory_filing_type("OTANNX", "Annual Report")
    fee_schedule = factory_fee_schedule("OTANNX", "XX", "EN000X", datetime.now(tz=timezone.utc), None)
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
    fee_code = factory_feecode("EN000X", 100)
    corp_type = factory_corp_type("XX", "Cooperative")
    filing_type = factory_filing_type("OTANNX", "Annual Report")
    fee_schedule = factory_fee_schedule("OTANNX", "XX", "EN000X", datetime.now(tz=timezone.utc), None)
    session.add(fee_code)
    session.add(corp_type)
    session.add(filing_type)
    session.add(fee_schedule)
    session.commit()

    fee_schedule = fee_schedule.find_by_filing_type_and_corp_type("XX", "OTANNX")

    assert fee_schedule.fee.amount == 100


def test_fee_schedule_find_by_corp_type_and_filing_type_invalid(session):
    """Assert a valid fee schedule is stored correctly.

    Start with a blank database.
    """
    fee_code = factory_feecode("EN000X", 100)
    corp_type = factory_corp_type("XX", "Cooperative")
    filing_type = factory_filing_type("OTANNX", "Annual Report")
    fee_schedule = factory_fee_schedule("OTANNX", "XX", "EN000X", datetime.now(tz=timezone.utc), None)
    session.add(fee_code)
    session.add(corp_type)
    session.add(filing_type)
    session.add(fee_schedule)
    session.commit()

    fee_schedule = fee_schedule.find_by_filing_type_and_corp_type("XX", "OTADDX")

    assert fee_schedule is None


def test_fee_schedule_find_by_corp_type_and_filing_type_valid_date(session):
    """Assert a valid fee schedule is stored correctly.

    Start with a blank database.
    """
    fee_code = factory_feecode("EN000X", 100)
    corp_type = factory_corp_type("XX", "Cooperative")
    filing_type = factory_filing_type("OTANNX", "Annual Report")
    fee_schedule = factory_fee_schedule("OTANNX", "XX", "EN000X", datetime.now(tz=timezone.utc), None)
    session.add(fee_code)
    session.add(corp_type)
    session.add(filing_type)
    session.add(fee_schedule)
    session.commit()

    fee_schedule = fee_schedule.find_by_filing_type_and_corp_type("XX", "OTANNX", datetime.now(tz=timezone.utc))

    assert fee_schedule.fee.amount == 100


def test_fee_schedule_find_by_corp_type_and_filing_type_invalid_date(session):
    """Assert a valid fee schedule is stored correctly.

    Start with a blank database.
    """
    now = datetime.now(tz=timezone.utc)
    fee_code = factory_feecode("EN000X", 100)
    corp_type = factory_corp_type("XX", "Cooperative")
    filing_type = factory_filing_type("OTANNX", "Annual Report")
    fee_schedule = factory_fee_schedule("OTANNX", "XX", "EN000X", now, None)
    session.add(fee_code)
    session.add(corp_type)
    session.add(filing_type)
    session.add(fee_schedule)
    session.commit()

    fee_schedule = fee_schedule.find_by_filing_type_and_corp_type(
        "XX", "OTANNX", datetime.now(tz=timezone.utc) - timedelta(1)
    )

    assert fee_schedule is None


def test_fee_schedule_find_by_none_corp_type_and_filing_type(session):
    """Assert a valid fee schedule is stored correctly.

    Start with a blank database.
    """
    now = datetime.now(tz=timezone.utc)
    fee_code = factory_feecode("EN000X", 100)
    corp_type = factory_corp_type("XX", "Cooperative")
    filing_type = factory_filing_type("OTANNX", "Annual Report")
    fee_schedule = factory_fee_schedule("OTANNX", "XX", "EN000X", now, None)
    session.add(fee_code)
    session.add(corp_type)
    session.add(filing_type)
    session.add(fee_schedule)
    session.commit()

    fee_schedule = fee_schedule.find_by_filing_type_and_corp_type(None, None)

    assert fee_schedule is None


def get_or_create_corp_type(corp_type_code: str, corp_description: str, session):
    """Return a valid Corp Type object."""
    existing = session.query(CorpType).filter_by(code=corp_type_code).first()
    if existing:
        return existing
    return CorpType(code=corp_type_code, description=corp_description)


def test_get_fee_details_all_products(session):
    """Test the get_fee_details method without providing specific product code -> found all the record."""
    fee_code = factory_feecode("EN000X", 100)
    service_fee_code = factory_feecode("SRV001", 10)
    corp_type = get_or_create_corp_type("BEN", "Benefit Company", session=session)
    filing_type = factory_filing_type("OTF", "Notice of Change")
    fee_schedule = factory_fee_schedule(
        filing_type_code="OTF",
        corp_type_code="BEN",
        fee_code="EN000X",
        fee_start_date=datetime.now(tz=timezone.utc),
        fee_end_date=None,
        service_fee_code="SRV001",
    )

    session.add(fee_code)
    session.add(service_fee_code)
    session.add(corp_type)
    session.add(filing_type)
    session.add(fee_schedule)
    session.commit()

    results = fee_schedule.get_fee_details()

    assert len(results) >= 1
    target_result = None
    for result in results:
        if (
            result.corp_type == "BEN"
            and result.filing_type == "OTF"
            and result.corp_type_description == "Benefit Company"
            and result.service == "Notice of Change"
            and result.fee == 100
            and result.service_charge == 10
            and result.total_gst == 0
        ):
            target_result = result
            break

    assert target_result is not None, "Expected record with specific conditions not found"
    assert target_result.corp_type == "BEN"
    assert target_result.filing_type == "OTF"
    assert target_result.corp_type_description == "Benefit Company"
    assert target_result.service == "Notice of Change"
    assert target_result.fee == 100
    assert target_result.service_charge == 10
    assert target_result.total_gst == 0


def test_get_fee_details_specific_product_code(session):
    """Test the get_fee_details method with specific product code , found the record with provided product code."""
    fee_code = factory_feecode("EN000X", 100)
    service_fee_code = factory_feecode("SRV001", 10)
    corp_type = get_or_create_corp_type("BEN", "Benefit Company", session=session)
    product_code = corp_type.product
    filing_type = factory_filing_type("OTF", "Notice of Change")
    fee_schedule = factory_fee_schedule(
        filing_type_code="OTF",
        corp_type_code="BEN",
        fee_code="EN000X",
        fee_start_date=datetime.now(tz=timezone.utc),
        fee_end_date=None,
        service_fee_code="SRV001",
    )

    session.add(fee_code)
    session.add(service_fee_code)
    session.add(corp_type)
    session.add(filing_type)
    session.add(fee_schedule)
    session.commit()

    results = fee_schedule.get_fee_details(product_code)

    assert len(results) >= 1
    target_result = None
    for result in results:
        if (
            result.corp_type == "BEN"
            and result.filing_type == "OTF"
            and result.corp_type_description == "Benefit Company"
            and result.service == "Notice of Change"
            and result.fee == 100
            and result.service_charge == 10
            and result.total_gst == 0
            and result.product_code == product_code
        ):
            target_result = result
            break

    assert target_result is not None, "Expected record with specific conditions not found"
    assert target_result.corp_type == "BEN"
    assert target_result.filing_type == "OTF"
    assert target_result.corp_type_description == "Benefit Company"
    assert target_result.service == "Notice of Change"
    assert target_result.fee == 100
    assert target_result.service_charge == 10
    assert target_result.total_gst == 0
