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

"""Tests to assure the StalePaymentTask.

Test-Suite to ensure that the StalePaymentTask is working as expected.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, PaymentStatus, TransactionStatus
from tasks.stale_payment_task import StalePaymentTask

from .factory import factory_create_pad_account, factory_invoice, factory_invoice_reference, factory_payment


@pytest.mark.parametrize(
    "payment_method,transaction_status,test_description,account_locked",
    [
        (
            PaymentMethod.DIRECT_PAY.value,
            TransactionStatus.FAILED.value,
            "DIRECT_PAY invoice with FAILED transaction",
            False,
        ),
        (
            PaymentMethod.DIRECT_PAY.value,
            TransactionStatus.CREATED.value,
            "DIRECT_PAY invoice with CREATED transaction",
            False,
        ),
        (
            PaymentMethod.CC.value,
            TransactionStatus.FAILED.value,
            "CC invoice with FAILED transaction and locked account",
            True,
        ),
    ],
)
def test_verify_created_credit_card_invoices(
    session, payment_method, transaction_status, test_description, account_locked
):
    """Test _verify_created_credit_card_invoices for different payment methods and transaction statuses."""
    account = factory_create_pad_account(auth_account_id="1234", payment_method=payment_method)

    if account_locked:
        account.has_nsf_invoices = datetime.now(tz=UTC) - timedelta(days=15)
        account.save()

    cfs_account = CfsAccountModel.find_by_account_id(account.id)[0]

    invoice = factory_invoice(
        payment_account=account,
        status_code=InvoiceStatus.CREATED.value,
        payment_method_code=payment_method,
        created_on=datetime.now(tz=UTC) - timedelta(days=1),
        total=50.0,
        paid=0.0,
        cfs_account_id=cfs_account.id,
    )
    invoice_number = "TEST-" + str(invoice.id)

    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number, status_code="ACTIVE")

    payment = factory_payment(
        payment_system_code="PAYBC",
        payment_method_code=payment_method,
        payment_status_code=PaymentStatus.CREATED.value,
        invoice_number=invoice_number,
        payment_account_id=account.id,
        invoice_amount=50.0,
    )

    transaction = PaymentTransactionModel(
        payment_id=payment.id,
        status_code=transaction_status,
        pay_system_reason_code="NSF" if payment_method == PaymentMethod.CC.value else "DECLINED",
    ).save()

    with patch("pay_api.services.direct_pay_service.DirectPayService.get_receipt") as mock_get_receipt:
        mock_receipt = ("TEST123", datetime.now(tz=UTC), 50.0)
        mock_get_receipt.return_value = mock_receipt

        StalePaymentTask._verify_created_credit_card_invoices(daily_run=True)

    if account_locked:
        updated_account = PaymentAccountModel.find_by_id(account.id)
        assert not updated_account.has_nsf_invoices

    assert transaction.id is not None
    assert transaction.status_code == TransactionStatus.COMPLETED.value

    assert invoice.id is not None
    assert invoice.invoice_status_code == InvoiceStatus.PAID.value

    assert payment.id is not None
    assert payment.payment_status_code == PaymentStatus.COMPLETED.value
