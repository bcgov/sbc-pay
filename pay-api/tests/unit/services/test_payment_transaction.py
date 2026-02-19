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

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from pay_api.exceptions import BusinessException
from pay_api.models import CfsAccount, FeeSchedule, Invoice, Payment
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.services.hashing import HashingService
from pay_api.services.invoice import Invoice as InvoiceService
from pay_api.services.payment_service import Payment as PaymentService
from pay_api.services.payment_transaction import PaymentTransaction as PaymentTransactionService
from pay_api.utils.enums import (
    CfsAccountStatus,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    TransactionStatus,
)
from pay_api.utils.errors import Error
from tests import skip_in_pod
from tests.utilities.base_test import (
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
    factory_payment_transaction,
    get_paybc_transaction_request,
)


def test_transaction_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    payment = factory_payment(invoice_number=invoice_reference.invoice_number).save()

    payment_transaction = PaymentTransactionService()
    payment_transaction.status_code = "CREATED"
    payment_transaction.transaction_end_time = datetime.now(tz=UTC)
    payment_transaction.transaction_start_time = datetime.now(tz=UTC)
    payment_transaction.pay_system_url = "http://google.com"
    payment_transaction.client_system_url = "http://google.com"
    payment_transaction.payment_id = payment.id
    payment_transaction = payment_transaction.save()

    transaction = PaymentTransactionService.find_by_id(payment_transaction.id)

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.transaction_end_time is not None


def test_transaction_create_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    payment = factory_payment(invoice_number=invoice_reference.invoice_number).save()

    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id == payment.id
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.asdict() is not None


def test_transaction_for_direct_pay_create_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.DIRECT_PAY.value)
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id).save()

    factory_payment(invoice_number=invoice_reference.invoice_number).save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.asdict() is not None


def test_transaction_create_from_invalid_payment(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id).save()

    factory_payment(invoice_number=invoice_reference.invoice_number).save()

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    with pytest.raises(BusinessException) as excinfo:
        PaymentTransactionService.create_transaction_for_invoice(999, get_paybc_transaction_request())
    assert excinfo.value.code == Error.INVALID_INVOICE_ID.name


@skip_in_pod
def test_transaction_update(session, public_user_mock):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    payment: Payment = factory_payment(
        invoice_number=invoice_reference.invoice_number,
        payment_account_id=payment_account.id,
    ).save()

    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())
    transaction = PaymentTransactionService.update_transaction(transaction.id, pay_response_url="receipt_number=123451")

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.transaction_end_time is not None
    assert transaction.status_code == TransactionStatus.COMPLETED.value
    assert payment.receipt_number


@skip_in_pod
def test_transaction_update_with_no_receipt(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()
    cfs_account = CfsAccount.find_by_account_id(payment_account.id)[0]
    invoice = factory_invoice(payment_account)
    invoice.cfs_account_id = cfs_account.id
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id, invoice_number="REG123").save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    factory_payment(
        invoice_number=invoice_reference.invoice_number,
        payment_account_id=payment_account.id,
    ).save()

    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())
    transaction = PaymentTransactionService.update_transaction(transaction.id, pay_response_url=None)

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.transaction_end_time is not None
    assert transaction.status_code == TransactionStatus.FAILED.value
    assert transaction.asdict() is not None


@skip_in_pod
def test_transaction_update_completed(session, public_user_mock):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    factory_payment(
        invoice_number=invoice_reference.invoice_number,
        payment_account_id=payment_account.id,
    ).save()

    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())
    transaction = PaymentTransactionService.update_transaction(transaction.id, pay_response_url="receipt_number=123451")

    with pytest.raises(BusinessException) as excinfo:
        PaymentTransactionService.update_transaction(transaction.id, pay_response_url="receipt_number=123451")
    assert excinfo.value.code == Error.INVALID_TRANSACTION.name


def test_transaction_create_new_on_completed_payment(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    factory_payment(
        invoice_number=invoice_reference.invoice_number,
        payment_status_code=PaymentStatus.COMPLETED.value,
    ).save()

    with pytest.raises(BusinessException) as excinfo:
        PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())
    assert excinfo.value.code == Error.COMPLETED_PAYMENT.name


def test_multiple_transactions_for_single_payment(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())
    PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())
    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.status_code == TransactionStatus.CREATED.value


def test_transaction_invalid_lookup(session):
    """Invalid lookup.."""
    with pytest.raises(BusinessException) as excinfo:
        PaymentTransactionService.find_by_id(uuid.uuid4())
    assert excinfo.value.code == Error.INVALID_TRANSACTION_ID.name


def test_transaction_invalid_update(session):
    """Invalid update.."""
    with pytest.raises(BusinessException) as excinfo:
        PaymentTransactionService.update_transaction(uuid.uuid4(), pay_response_url=None)
    assert excinfo.value.code == Error.INVALID_TRANSACTION_ID.name


def test_transaction_find_active_lookup(session):
    """Invalid lookup.."""
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    payment = factory_payment(invoice_number=invoice_reference.invoice_number).save()

    transaction = factory_payment_transaction(payment.id, TransactionStatus.CREATED.value)
    transaction.save()

    transaction = PaymentTransactionService.find_by_invoice_id_and_status(invoice.id, TransactionStatus.CREATED.value)
    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.status_code == TransactionStatus.CREATED.value


def test_transaction_find_active_none_lookup(session):
    """Invalid lookup.."""
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    payment = factory_payment(invoice_number=invoice_reference.invoice_number).save()

    transaction = factory_payment_transaction(payment.id, TransactionStatus.COMPLETED.value)
    transaction.save()

    transaction = PaymentTransactionService.find_by_invoice_id_and_status(invoice.id, TransactionStatus.CREATED.value)
    assert transaction is None


def test_transaction_find_by_payment_id(session):
    """Find all transactions by payment id.."""
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_reference = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    payment = factory_payment(invoice_number=invoice_reference.invoice_number).save()

    transaction = factory_payment_transaction(payment.id, TransactionStatus.CREATED.value)
    transaction.save()

    transaction = PaymentTransactionService.find_by_invoice_id(invoice.id)
    assert transaction is not None
    assert transaction.get("items") is not None


def test_no_existing_transaction(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    transaction = PaymentTransactionService.find_by_invoice_id_and_status(invoice.id, TransactionStatus.CREATED.value)

    assert transaction is None


@skip_in_pod
def test_transaction_update_on_paybc_connection_error(session):
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

    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())

    from unittest.mock import patch

    from requests.exceptions import ConnectionError, ConnectTimeout

    # Mock here that the invoice update fails here to test the rollback scenario
    with patch(
        "pay_api.services.oauth_service.requests.post",
        side_effect=ConnectionError("mocked error"),
    ):
        transaction = PaymentTransactionService.update_transaction(transaction.id, pay_response_url=None)
        assert transaction.pay_system_reason_code == "SERVICE_UNAVAILABLE"
    with patch(
        "pay_api.services.oauth_service.requests.post",
        side_effect=ConnectTimeout("mocked error"),
    ):
        transaction = PaymentTransactionService.update_transaction(transaction.id, pay_response_url=None)
        assert transaction.pay_system_reason_code == "SERVICE_UNAVAILABLE"

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.transaction_end_time is not None
    assert transaction.status_code == TransactionStatus.FAILED.value


@skip_in_pod
def test_update_transaction_for_direct_pay_with_response_url(session):
    """Assert that the receipt records are created."""
    response_url = (
        "trnApproved=1&messageText=Approved&trnOrderId=1003598&trnAmount=201.00&paymentMethod=CC"
        "&cardType=VI&authCode=TEST&trnDate=2020-08-11&pbcTxnNumber=1"
    )
    valid_hash = f"&hashValue={HashingService.encode(response_url)}"

    payment_account = factory_payment_account(payment_method_code=PaymentMethod.DIRECT_PAY.value)
    payment = factory_payment(payment_method_code=PaymentMethod.DIRECT_PAY.value)
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())

    # Update transaction with invalid hash
    transaction = PaymentTransactionService.update_transaction(transaction.id, f"{response_url}1234567890")
    assert transaction.status_code == TransactionStatus.FAILED.value

    # Update transaction with valid hash
    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())
    transaction = PaymentTransactionService.update_transaction(transaction.id, f"{response_url}{valid_hash}")
    assert transaction.status_code == TransactionStatus.COMPLETED.value


@skip_in_pod
def test_update_transaction_for_direct_pay_without_response_url(session):
    """Assert that the receipt records are created."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.DIRECT_PAY.value)
    payment = factory_payment(payment_method_code=PaymentMethod.DIRECT_PAY.value)
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())

    # Update transaction without response url, which should update the receipt
    transaction = PaymentTransactionService.update_transaction(transaction.id, None)
    assert transaction.status_code == TransactionStatus.COMPLETED.value


@skip_in_pod
def test_event_failed_transactions(session, public_user_mock, monkeypatch):
    """Assert that the transaction status is EVENT_FAILED when Q is not available."""
    # 1. Create payment records
    # 2. Create a transaction
    # 3. Fail the queue publishing which will mark the payment as COMPLETED and transaction as EVENT_FAILED
    # 4. Update the transansaction with queue up which will mark the transaction as COMPLETED
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.DIRECT_PAY.value)
    payment_account.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")

    invoice = factory_invoice(payment_account, total=30)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    transaction = PaymentTransactionService.create_transaction_for_invoice(invoice.id, get_paybc_transaction_request())

    def get_receipt(cls, payment_account, pay_response_url: str, invoice_reference):  # pylint: disable=unused-argument; mocks of library methods
        return "1234567890", datetime.now(tz=UTC), 30.00

    monkeypatch.setattr("pay_api.services.direct_sale_service.DirectSaleService.get_receipt", get_receipt)

    with patch(
        "pay_api.services.gcp_queue_publisher.publish_to_queue",
        side_effect=ConnectionError("mocked error"),
    ):
        transaction = PaymentTransactionService.update_transaction(transaction.id, pay_response_url="?key=value")

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.transaction_end_time is not None
    assert transaction.status_code == TransactionStatus.EVENT_FAILED.value

    # Now update the transaction and check the status of the transaction
    transaction = PaymentTransactionService.update_transaction(transaction.id, pay_response_url=None)

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.transaction_end_time is not None
    assert transaction.status_code == TransactionStatus.COMPLETED.value


def test_create_transaction_for_nsf_payment(session):
    """Assert that the payment is saved to the table."""
    # Create a FAILED payment (NSF), then clone the payment to create another one for CC payment
    # Create a transaction and assert it's success.
    inv_number_1 = "REG00001"
    payment_account = factory_payment_account().save()
    invoice_1 = factory_invoice(payment_account, total=100)
    invoice_1.save()
    factory_payment_line_item(invoice_id=invoice_1.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number_1).save()
    payment_1 = factory_payment(
        payment_status_code="FAILED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_1,
        invoice_amount=100,
        payment_method_code=PaymentMethod.PAD.value,
    )
    payment_1.save()

    # Create payment for NSF payment.
    payment_2 = factory_payment(
        payment_account_id=payment_account.id,
        invoice_number=inv_number_1,
        invoice_amount=100,
        payment_method_code=PaymentMethod.CC.value,
    )
    payment_2.save()

    transaction = PaymentTransactionService.create_transaction_for_payment(
        payment_2.id, get_paybc_transaction_request()
    )

    assert transaction is not None
    assert transaction.id is not None
    assert transaction.status_code is not None
    assert transaction.payment_id is not None
    assert transaction.client_system_url is not None
    assert transaction.pay_system_url is not None
    assert transaction.transaction_start_time is not None
    assert transaction.asdict() is not None


def test_create_transaction_for_completed_nsf_payment(session):
    """Assert that the payment is saved to the table."""
    # Create a FAILED payment (NSF), then clone the payment to create another one for CC payment
    # Create a transaction and assert it's success.
    inv_number_1 = "REG00001"
    payment_account = factory_payment_account().save()
    invoice_1 = factory_invoice(payment_account, total=100)
    invoice_1.save()
    factory_payment_line_item(invoice_id=invoice_1.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number_1).save()
    payment_1 = factory_payment(
        payment_status_code="FAILED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_1,
        invoice_amount=100,
        payment_method_code=PaymentMethod.PAD.value,
    )
    payment_1.save()

    # Create payment for NSF payment.
    payment_2 = factory_payment(
        payment_status_code="COMPLETED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_1,
        invoice_amount=100,
        payment_method_code=PaymentMethod.CC.value,
    )
    payment_2.save()

    with pytest.raises(BusinessException) as excinfo:
        PaymentTransactionService.create_transaction_for_payment(payment_2.id, get_paybc_transaction_request())

    assert excinfo.value.code == Error.INVALID_PAYMENT_ID.name


def test_patch_transaction_for_nsf_payment(session, monkeypatch):
    """Assert that the payment is saved to the table."""
    # Create a FAILED payment (NSF), then clone the payment to create another one for CC payment
    # Create a transaction and assert it's success.
    # Patch transaction and check the status of records
    inv_number_1 = "REG00001"
    payment_account = factory_payment_account(
        cfs_account_status=CfsAccountStatus.FREEZE.value,
        payment_method_code="PAD",
        has_nsf_invoices=datetime.now(tz=UTC),
    ).save()
    invoice_1 = factory_invoice(payment_account, total=100)
    invoice_1.save()
    factory_payment_line_item(invoice_id=invoice_1.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number_1).save()

    nsf_charge_invoice = factory_invoice(payment_account, total=30, paid=30, payment_method_code=PaymentMethod.CC.value)
    nsf_charge_invoice.save()
    factory_payment_line_item(invoice_id=nsf_charge_invoice.id, fee_schedule_id=1).save()
    factory_invoice_reference(nsf_charge_invoice.id, invoice_number=inv_number_1).save()

    payment_1 = factory_payment(
        payment_status_code="FAILED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_1,
        invoice_amount=100,
        payment_method_code=PaymentMethod.PAD.value,
    )
    payment_1.save()

    # Create payment for NSF payment.
    payment_2 = factory_payment(
        payment_status_code="CREATED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_1,
        invoice_amount=100,
        payment_method_code=PaymentMethod.CC.value,
    )
    payment_2.save()

    def get_receipt(cls, payment_account, pay_response_url: str, invoice_reference):  # pylint: disable=unused-argument; mocks of library methods
        return "1234567890", datetime.now(tz=UTC), 100.00

    monkeypatch.setattr("pay_api.services.direct_pay_service.DirectPayService.get_receipt", get_receipt)
    txn = PaymentTransactionService.create_transaction_for_payment(payment_2.id, get_paybc_transaction_request())
    txn = PaymentTransactionService.update_transaction(txn.id, pay_response_url="receipt_number=123451")

    assert txn.status_code == "COMPLETED"
    payment_2 = Payment.find_by_id(payment_2.id)
    assert payment_2.payment_status_code == "COMPLETED"

    invoice_1 = Invoice.find_by_id(invoice_1.id)
    assert invoice_1.invoice_status_code == "PAID"
    cfs_account = CfsAccount.find_effective_by_payment_method(payment_account.id, PaymentMethod.PAD.value)
    assert cfs_account.status == "ACTIVE"
    assert payment_account.has_nsf_invoices is None


def test_patch_transaction_for_eft_overdue(session, monkeypatch):
    """Assert we can unlock for EFT."""
    inv_number_1 = "REG00001"
    payment_account = factory_payment_account(
        cfs_account_status=CfsAccountStatus.ACTIVE.value,
        payment_method_code=PaymentMethod.EFT.value,
        has_overdue_invoices=datetime.now(tz=UTC),
    ).save()
    invoice_1 = factory_invoice(payment_account, total=100, status_code=InvoiceStatus.APPROVED.value)
    invoice_1.save()
    invoice_2 = factory_invoice(payment_account, total=100, status_code=InvoiceStatus.OVERDUE.value)
    invoice_2.save()
    factory_payment_line_item(invoice_id=invoice_1.id, fee_schedule_id=1).save()
    factory_payment_line_item(invoice_id=invoice_2.id, fee_schedule_id=1).save()
    original_invoice_reference = factory_invoice_reference(invoice_2.id, invoice_number=inv_number_1).save()

    def get_receipt(cls, payment_account, pay_response_url: str, invoice_reference):  # pylint: disable=unused-argument; mocks of library methods
        return "1234567890", datetime.now(tz=UTC), 100.00

    monkeypatch.setattr("pay_api.services.direct_pay_service.DirectPayService.get_receipt", get_receipt)
    payment = PaymentService._consolidate_invoices_and_pay(  # pylint: disable=protected-access
        payment_account.auth_account_id, all_invoice_statuses=False
    )
    assert original_invoice_reference.status_code == InvoiceReferenceStatus.CANCELLED.value, (
        "Invoice reference should be CANCELLED a new invoice reference should be created"
    )

    txn = PaymentTransactionService.create_transaction_for_payment(payment.id, get_paybc_transaction_request())
    txn = PaymentTransactionService.update_transaction(txn.id, pay_response_url="receipt_number=123451")

    assert txn.status_code == InvoiceReferenceStatus.COMPLETED.value
    payment = Payment.find_by_id(payment.id)
    assert payment.payment_status_code == InvoiceReferenceStatus.COMPLETED.value

    invoice_1 = Invoice.find_by_id(invoice_1.id)
    assert invoice_1.invoice_status_code == InvoiceStatus.APPROVED.value, "APPROVED should not be updated"
    invoice_2 = Invoice.find_by_id(invoice_2.id)
    assert invoice_2.invoice_status_code == InvoiceStatus.PAID.value, "OVERDUE invoice should be PAID"
    assert payment_account.has_overdue_invoices is None, "This flag should be cleared."


def test_update_receipt_details_creates_invoice_reference_when_missing(session):
    """Assert that _update_receipt_details creates an invoice reference when one doesn't exist for an invoice."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.DIRECT_PAY.value)
    payment_account.save()

    invoice = factory_invoice(payment_account, total=100)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    # Deliberately do NOT create an invoice reference for this invoice
    payment = factory_payment(
        payment_account_id=payment_account.id,
        invoice_amount=100,
        payment_method_code=PaymentMethod.DIRECT_PAY.value,
    ).save()

    transaction_dao = factory_payment_transaction(payment.id, TransactionStatus.CREATED.value)
    transaction_dao.save()

    receipt_details = ("1234567890", datetime.now(tz=UTC), 100.00)

    invoice_service = InvoiceService()
    invoice_service._dao = invoice  # pylint: disable=protected-access

    PaymentTransactionService._update_receipt_details([invoice_service], payment, receipt_details, transaction_dao)

    assert transaction_dao.status_code == TransactionStatus.COMPLETED.value

    updated_invoice = Invoice.find_by_id(invoice.id)
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value

    new_ref = InvoiceReferenceModel.find_by_invoice_id_and_status(invoice.id, InvoiceReferenceStatus.COMPLETED.value)
    assert new_ref is not None
