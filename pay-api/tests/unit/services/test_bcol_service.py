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

"""Tests to assure the BCOL service layer.

Test-Suite to ensure that the BCOL Service layer is working as expected.
"""

from pay_api.models.fee_schedule import FeeSchedule
from pay_api.services.bcol_service import BcolService
from tests.utilities.base_test import (
    factory_invoice, factory_invoice_reference, factory_payment, factory_payment_account, factory_payment_line_item,
    get_auth_premium_user)


bcol_service = BcolService()


def test_create_account(session):
    """Test create_account."""
    account = bcol_service.create_account(None, None, get_auth_premium_user())
    assert account is not None


def test_get_payment_system_url(session):
    """Test get_payment_system_url."""
    url = bcol_service.get_payment_system_url(None, None, None)
    assert url is None


def test_get_payment_system_code(session):
    """Test get_payment_system_code."""
    code = bcol_service.get_payment_system_code()
    assert code == 'BCOL'


def test_create_invoice(session):
    """Test create_invoice."""
    pay_account = factory_payment_account(payment_system_code='BCOL', account_number='BCOL_ACC_1', bcol_user_id='test')
    pay_account.save()
    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_id=payment.id, account_id=pay_account.id)
    i.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(i.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    # payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice_id: str, **kwargs
    inv = bcol_service.create_invoice(pay_account, [line], i.id, filing_info={'folioNumber': '1234567890'})
    assert inv is not None
    assert inv.get('invoice_number') == 'TEST'


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
    pay_account = factory_payment_account(payment_system_code='BCOL', account_number='BCOL_ACC_1', bcol_user_id='test')
    pay_account.save()
    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_id=payment.id, account_id=pay_account.id)
    i.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(i.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    inv_ref = factory_invoice_reference(i.id).save()

    receipt = bcol_service.get_receipt(pay_account, None, inv_ref)
    assert receipt is not None
