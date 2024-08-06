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

import pytest

from pay_api.exceptions import BusinessException
from pay_api.models import FeeSchedule
from pay_api.services.invoice import Invoice as Invoice_service
from pay_api.utils.enums import PaymentMethod, PaymentStatus
from tests.utilities.base_test import (
    factory_invoice, factory_payment, factory_payment_account, factory_payment_line_item)


def test_invoice_eft_created_return_completed(session):
    """Assert that the invoice is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    i = factory_invoice(payment_account=payment_account, payment_method_code=PaymentMethod.EFT.value)
    i.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(i.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    invoice = Invoice_service.find_by_id(i.id, skip_auth_check=True).asdict()

    assert invoice is not None
    assert invoice['payment_method'] == PaymentMethod.EFT.value
    assert invoice['status_code'] == PaymentStatus.COMPLETED.value


def test_invoice_saved_from_new(session):
    """Assert that the invoice is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    i = factory_invoice(payment_account=payment_account)
    i.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(i.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    invoice = Invoice_service.find_by_id(i.id, skip_auth_check=True)

    assert invoice is not None
    assert invoice.id is not None
    assert invoice.invoice_status_code is not None
    assert invoice.refund is None
    assert invoice.payment_date is None
    assert invoice.total is not None
    assert invoice.paid is None
    assert invoice.payment_line_items is not None
    assert invoice.folio_number is not None
    assert invoice.business_identifier is not None


def test_invoice_invalid_lookup(session):
    """Test invalid lookup."""
    with pytest.raises(BusinessException) as excinfo:
        Invoice_service.find_by_id(999, skip_auth_check=True)
    assert excinfo.type == BusinessException


def test_invoice_find_by_id(session):
    """Assert that the invoice is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()
    i = factory_invoice(payment_account=payment_account)
    i.save()

    invoice = Invoice_service.find_by_id(i.id, skip_auth_check=True)

    assert invoice is not None
    assert invoice.id is not None
    assert invoice.invoice_status_code is not None
    assert invoice.refund is None
    assert invoice.payment_date is None
    assert invoice.total is not None
    assert invoice.paid is None
    assert not invoice.payment_line_items


def test_invoice_with_temproary_business_identifier(session):
    """Assert that the invoice dictionary is not include temproary business identifier."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    i = factory_invoice(payment_account=payment_account, business_identifier='Tzxcasd')
    i.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(i.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    invoice = Invoice_service.find_by_id(i.id, skip_auth_check=True)
    assert invoice is not None
    assert invoice.id is not None
    assert invoice.invoice_status_code is not None
    assert invoice.refund is None
    assert invoice.payment_date is None
    assert invoice.total is not None
    assert invoice.paid is None
    assert invoice.payment_line_items is not None
    assert invoice.folio_number is not None
    assert invoice.business_identifier is not None
    invoice_dict = invoice.asdict()
    assert invoice_dict.get('business_identifier') is None
