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

"""Tests to assure the Distribution code Service.

Test-Suite to ensure that the Distribution code Service is working as expected.
"""

from datetime import datetime, timezone

from pay_api import services
from pay_api.models import FeeSchedule
from pay_api.models import Invoice as InvoiceModel
from pay_api.services.payment_transaction import PaymentTransaction as PaymentTransactionService
from pay_api.utils.enums import InvoiceStatus, PaymentMethod
from tests.utilities.base_test import (
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
    get_distribution_code_payload,
    get_paybc_transaction_request,
)

test_user_token = {"preferred_username": "test"}


def test_distribution_code_saved_from_new(session, public_user_mock):
    """Assert that the fee schedule is saved to the table."""
    distribution_code_svc = services.DistributionCode()
    distribution_code = distribution_code_svc.save_or_update(get_distribution_code_payload())
    assert distribution_code is not None
    assert distribution_code.get("client") == "100"


def test_create_distribution_to_fee_link(session, public_user_mock):
    """Assert that the fee schedule is saved to the table."""
    distribution_code_svc = services.DistributionCode()
    distribution_code = distribution_code_svc.save_or_update(get_distribution_code_payload())
    assert distribution_code is not None
    distribution_id = distribution_code.get("distribution_code_id")

    distribution_code_svc.create_link(
        [{"feeScheduleId": 1}, {"feeScheduleId": 2}, {"feeScheduleId": 3}],
        distribution_id,
    )

    schedules = distribution_code_svc.find_fee_schedules_by_distribution_id(distribution_id)
    assert len(schedules.get("items")) == 3


def test_update_distribution(session, public_user_mock, monkeypatch):
    """Assert that the invoice status is updated when the distribution is updated."""
    # 1. Create a distribution code
    # 2. Attach a fee schedule to the distribution
    # 3. Create and complete payment
    # 4. Update the distribution and assert the invoice status is changed.
    distribution_code_svc = services.DistributionCode()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")

    # Create a direct pay
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.DIRECT_PAY.value)
    payment_account.save()

    invoice = factory_invoice(payment_account, total=30)
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id).save()
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    factory_payment(
        invoice_number=invoice_reference.invoice_number,
        payment_method_code=PaymentMethod.DIRECT_PAY.value,
        payment_account_id=payment_account.id,
        invoice_amount=30,
    ).save()

    distribution_id = line.fee_distribution_id

    distribution_code = distribution_code_svc.find_by_id(distribution_id)

    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())

    def get_receipt(
        cls, payment_account, pay_response_url: str, invoice_reference
    ):  # pylint: disable=unused-argument; mocks of library methods
        return "1234567890", datetime.now(tz=timezone.utc), 30.00

    monkeypatch.setattr("pay_api.services.direct_pay_service.DirectPayService.get_receipt", get_receipt)

    # Update transaction without response url, which should update the receipt
    PaymentTransactionService.update_transaction(transaction.id, pay_response_url=None)

    invoice = InvoiceModel.find_by_id(invoice.id)
    assert invoice.invoice_status_code == InvoiceStatus.PAID.value

    # Update distribution code
    distribution_code["client"] = "000"
    distribution_code_svc.save_or_update(distribution_code, distribution_id)
    invoice = InvoiceModel.find_by_id(invoice.id)
    assert invoice.invoice_status_code == InvoiceStatus.UPDATE_REVENUE_ACCOUNT.value

    invoice.invoice_status_code = InvoiceStatus.REFUNDED.value
    # Update distribution code
    distribution_code["client"] = "001"
    distribution_code_svc.save_or_update(distribution_code, distribution_id)
    invoice = InvoiceModel.find_by_id(invoice.id)
    assert invoice.invoice_status_code == InvoiceStatus.UPDATE_REVENUE_ACCOUNT_REFUND.value
