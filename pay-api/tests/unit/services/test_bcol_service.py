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

"""Tests to assure the BCOL service layer.

Test-Suite to ensure that the BCOL Service layer is working as expected.
"""

import pytest
from pay_api.models.fee_schedule import FeeSchedule
from pay_api.services.bcol_service import BcolService
from pay_api.services.payment_line_item import PaymentLineItem
from tests.utilities.base_test import (
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
)


bcol_service = BcolService()


def test_create_account(session):
    """Test create_account."""
    account = bcol_service.create_account(
        identifier=None, contact_info=None, payment_info=None
    )
    assert not account


def test_get_payment_system_code(session):
    """Test get_payment_system_code."""
    code = bcol_service.get_payment_system_code()
    assert code == "BCOL"


@pytest.mark.parametrize(
    "test_name, service_fees",
    [
        ("Greater than 1.5 (Invalid, but still executes)", 2.0),
        ("$1.50 service fee", 1.5),
        ("$1.05 service fee (ESRA)", 1.05),
        ("$1 service fee", 1),
        ("No service fee", 0),
    ],
)
def test_create_invoice(session, test_name, service_fees):
    """Test create_invoice."""
    pay_account = factory_payment_account(
        payment_system_code="BCOL", account_number="BCOL_ACC_1", bcol_user_id="test"
    )
    pay_account.save()
    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=pay_account, service_fees=service_fees)
    i.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(i.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    line = PaymentLineItem.find_by_id(line.id)
    inv = bcol_service.create_invoice(
        payment_account=pay_account,
        line_items=[line],
        invoice=i,
        filing_info={"folioNumber": "1234567890"},
        corp_type_code=i.corp_type_code,
        business_identifier=i.business_identifier,
    )
    assert inv is not None
    assert inv.invoice_number == "TEST"


def test_update_invoice(session):
    """Test update_invoice."""
    bcol_service.update_invoice(None, None, None, None)
    assert True


def test_cancel_invoice(session):
    """Test cancel_invoice."""
    bcol_service.cancel_invoice(None, None)
    assert True


def test_get_receipt(session):
    """Test cancel_invoice."""
    pay_account = factory_payment_account(
        payment_system_code="BCOL", account_number="BCOL_ACC_1", bcol_user_id="test"
    )
    pay_account.save()
    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=pay_account)
    i.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(i.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    inv_ref = factory_invoice_reference(i.id).save()

    receipt = bcol_service.get_receipt(pay_account, None, inv_ref)
    assert receipt is not None
