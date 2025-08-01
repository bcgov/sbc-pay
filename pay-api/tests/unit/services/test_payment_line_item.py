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

from decimal import Decimal
from unittest.mock import patch

import pytest

from pay_api.models import CorpType, FeeCode, FeeSchedule, FilingType, Invoice, InvoiceSchema, TaxRate
from pay_api.services.fee_schedule import FeeSchedule as FeeScheduleService
from pay_api.services.payment_line_item import PaymentLineItem as PaymentLineService
from pay_api.utils.enums import LineItemStatus
from tests.utilities.base_test import (
    factory_fee_schedule_model,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
)


def test_line_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    line = factory_payment_line_item(
        invoice.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        status=LineItemStatus.CANCELLED.value,
    )
    line.save()

    p = PaymentLineService.find_by_id(line.id)

    assert p is not None
    assert p.id is not None
    assert p.invoice_id is not None
    assert p.filing_fees is not None
    assert p.fee_schedule_id is not None
    assert p.gst is None
    assert p.pst is None
    assert p.line_item_status_code is not None
    assert p.priority_fees is None
    assert p.future_effective_fees is None
    invoice = Invoice.find_by_id(invoice.id)
    schema = InvoiceSchema()
    d = schema.dump(invoice)
    assert d.get("id") == invoice.id
    assert len(d.get("line_items")) == 1


def test_line_invalid_lookup(session):
    """Test Invalid lookup."""
    p = PaymentLineService.find_by_id(999)

    assert p is not None
    assert p.id is None


@pytest.mark.parametrize(
    "gst_added,has_service_fees,expected_filing_fees,expected_service_fees,expected_statutory_gst,expected_service_gst,test_id",
    [
        (True, False, 100.00, 0.00, 5.00, 0.00, "gst_enabled_no_service"),
        (False, False, 100.00, 0.00, 0.00, 0.00, "gst_disabled_no_service"),
        (True, True, 100.00, 10.00, 5.00, 0.50, "gst_enabled_with_service"),
    ],
    ids=lambda x: x[-1] if isinstance(x, tuple) else str(x),
)
def test_payment_line_item_gst_calculation(
    session,
    gst_added,
    has_service_fees,
    expected_filing_fees,
    expected_service_fees,
    expected_statutory_gst,
    expected_service_gst,
    test_id,
):
    """Test GST calculation for payment line items based on fee schedule settings."""
    fee_code = FeeCode(code=f"TEST_FEE_{test_id}", amount=100.00)
    fee_code.save()

    service_fee_code = None
    if has_service_fees:
        service_fee_code = FeeCode(code=f"SERVICE_FEE_{test_id}", amount=10.00)
        service_fee_code.save()

    corp_type = CorpType(code=f"TEST_CORP_{test_id}", description=f"Test Corp Type {test_id}")
    corp_type.save()

    filing_type = FilingType(code=f"TEST_FILING_{test_id}", description=f"Test Filing Type {test_id}")
    filing_type.save()

    fee_schedule = factory_fee_schedule_model(
        filing_type=filing_type, corp_type=corp_type, fee_code=fee_code, service_fee=service_fee_code
    )
    fee_schedule.gst_added = gst_added
    fee_schedule.save()

    payment_account = factory_payment_account()
    payment_account.save()
    payment = factory_payment()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()

    # Mock GST rate for consistent testing (5% = 0.05)
    with patch.object(TaxRate, "get_current_gst_rate", return_value=Decimal("0.05")):
        fee_schedule_service = FeeScheduleService.find_by_corp_type_and_filing_type(
            corp_type.code, filing_type.code, include_service_fees=has_service_fees
        )

        line_item = PaymentLineService.create(invoice_id=invoice.id, fee_schedule=fee_schedule_service, filing_info={})
        line_item.save()

        saved_line_item = PaymentLineService.find_by_id(line_item.id)

        assert saved_line_item is not None
        assert saved_line_item.filing_fees == expected_filing_fees
        assert saved_line_item.service_fees == expected_service_fees
        assert saved_line_item.statutory_fees_gst == expected_statutory_gst
        assert saved_line_item.service_fees_gst == expected_service_gst
