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
from datetime import datetime, timedelta, timezone

import pytest
import pytz

from pay_api.models.payment_account import PaymentAccount
from pay_api.services.payment import Payment as PaymentService
from pay_api.services.payment_calculations import (
    build_grouped_invoice_context,
    build_statement_context,
    build_statement_summary_context,
    build_transaction_rows,
    calculate_invoice_summaries,
)
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, PaymentMethod
from pay_api.utils.util import current_local_time
from tests.utilities.base_test import (
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
    factory_statement,
    factory_usd_payment,
)

# noqa: I005


def test_payment_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    p = PaymentService.find_by_id(payment.id)

    assert p is not None
    assert p.id is not None
    assert p.payment_system_code is not None
    assert p.payment_method_code is not None
    assert p.payment_status_code is not None


def test_payment_invalid_lookup(session):
    """Test invalid lookup."""
    p = PaymentService.find_by_id(999)

    assert p is not None
    assert p.id is None


def test_payment_with_no_active_invoice(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account, InvoiceStatus.DELETED.value)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    p = PaymentService.find_by_id(payment.id)

    assert p is not None
    assert p.id is not None


@pytest.mark.parametrize(
    "test_name, search_filter, view_all, expected_total, expected_key, expected_value",
    [
        ("no_filter", {}, False, 3, "status_code", InvoiceStatus.CREATED.value),
        ("no_filter_view_all", {}, True, 4, "status_code", InvoiceStatus.CREATED.value),
        (
            "status_created",
            {"status": "CREATED"},
            False,
            3,
            "status_code",
            InvoiceStatus.CREATED.value,
        ),
        ("status_completed", {"status": "COMPLETED"}, False, 0, None, None),
        (
            "status_code_created",
            {"statusCode": "CREATED"},
            False,
            3,
            "status_code",
            InvoiceStatus.CREATED.value,
        ),
        ("status_code_completed", {"statusCode": "COMPLETED"}, False, 0, None, None),
        (
            "folio",
            {"folioNumber": "1234567890"},
            False,
            3,
            "folio_number",
            "1234567890",
        ),
        (
            "business_identifier",
            {"businessIdentifier": "CP000"},
            False,
            3,
            "business_identifier",
            "CP0001234",
        ),
        (
            "date",
            {
                "dateFilter": {
                    "createdFrom": datetime.now(tz=timezone.utc).strftime("%m/%d/%Y"),
                    "createdTo": datetime.now(tz=timezone.utc).strftime("%m/%d/%Y"),
                }
            },
            False,
            3,
            None,
            None,
        ),
        ("week_no_match", {"weekFilter": {"index": 2}}, False, 0, None, None),
        ("week_match_all", {"weekFilter": {"index": 0}}, False, 3, None, None),
        (
            "month",
            {
                "monthFilter": {
                    "month": current_local_time("America/Vancouver").month,
                    "year": current_local_time("America/Vancouver").year,
                }
            },
            False,
            3,
            None,
            None,
        ),
        ("created_by", {"createdBy": "1"}, False, 1, "created_by", "test"),
        ("created_name", {"createdName": "1"}, False, 1, "created_name", "1"),
        ("created_name_view_all", {"createdName": "1"}, True, 2, "created_name", "1"),
        ("line_items", {"lineItems": "test1"}, False, 1, None, None),
        ("line_items_view_all", {"lineItems": "test1"}, True, 2, None, None),
        ("details_value", {"details": "value1"}, False, 1, None, None),
        ("details_value_view_all", {"details": "value1"}, True, 2, None, None),
        ("details_label", {"details": "label1"}, False, 1, None, None),
        ("details_label_view_all", {"details": "label1"}, True, 2, None, None),
        (
            "line_items_and_details_1",
            {"lineItemsAndDetails": "test1"},
            False,
            1,
            None,
            None,
        ),
        (
            "line_items_and_details_2",
            {"lineItemsAndDetails": "label1"},
            False,
            1,
            None,
            None,
        ),
        (
            "line_items_and_details_3",
            {"lineItemsAndDetails": "value1"},
            False,
            1,
            None,
            None,
        ),
        ("id", None, False, 1, "id", None),
        (
            "payment_method_no_match",
            {"paymentMethod": PaymentMethod.CC.value},
            False,
            0,
            None,
            None,
        ),
        (
            "payment_method_match",
            {"paymentMethod": PaymentMethod.DIRECT_PAY.value},
            False,
            2,
            "payment_method",
            PaymentMethod.DIRECT_PAY.value,
        ),
        (
            "payment_method_match_view_all",
            {"paymentMethod": PaymentMethod.DIRECT_PAY.value},
            True,
            3,
            "payment_method",
            PaymentMethod.DIRECT_PAY.value,
        ),
        ("payment_method_nofee", {"paymentMethod": "NO_FEE"}, False, 1, None, None),
        ("invoice_number", {"invoiceNumber": "31"}, False, 1, "invoice_number", "1231"),
        (
            "invoice_number_view_all",
            {"invoiceNumber": "31"},
            True,
            2,
            "invoice_number",
            "1231",
        ),
        ("account_name", {"accountName": "account 1"}, False, 3, None, None),
        ("account_name_view_all_1", {"accountName": "account 2"}, True, 1, None, None),
        ("account_name_view_all_2", {"accountName": "account"}, True, 4, None, None),
        ("product", {"product": "BUSINESS"}, False, 3, "product", "BUSINESS"),
        ("product_view_all", {"product": "BUSINESS"}, True, 4, "product", "BUSINESS"),
        ("csv_export", {"product": "BUSINESS"}, True, 4, None, None),
    ],
)
def test_search_payment_history(
    session, executor_mock, test_name, search_filter, view_all, expected_total, expected_key, expected_value
):
    """Assert that the search payment history is working."""
    payment_account = factory_payment_account(name="account 1", auth_account_id="1")
    payment_account.save()
    # make 3 payments
    for i in range(3):
        invoice = factory_invoice(
            payment_account,
            created_name=i,
            total=i * 10,
            details=[{"label": f"label{i}", "value": f"value{i}"}],
        )
        invoice.save()
        if expected_key == "id" and not search_filter:
            search_filter = {"id": invoice.id}
            expected_value = invoice.id
        factory_invoice_reference(invoice_id=invoice.id, invoice_number=f"123{i}").save()
        line_item = factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=1, description=f"test{i}")
        line_item.save()

    # create another account with a payment
    payment_account2 = factory_payment_account(name="account 2", auth_account_id="2")
    payment_account2.save()
    invoice = factory_invoice(
        payment_account2,
        created_name="1",
        total=10,
        details=[{"label": "label1", "value": "value1"}],
    )
    invoice.save()
    if expected_key == "id" and not search_filter:
        search_filter = {"id": invoice.id}
        expected_value = invoice.id
    factory_invoice_reference(invoice.id, invoice_number="1231").save()
    line_item = factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=1, description="test1")
    line_item.save()

    auth_account_id = payment_account.auth_account_id if not view_all else None

    if test_name == "csv_export":
        return_all = True
    else:
        return_all = False
    limit = 2
    for additional_payload in [{}, {"excludeCounts": True}]:
        search_filter.update(additional_payload)
        results = PaymentService.search_purchase_history(
            auth_account_id=auth_account_id,
            search_filter=search_filter,
            limit=limit,
            page=1,
            return_all=return_all,
        )
        assert results is not None
        assert "items" in results, "'items' key is missing in results"
        if "excludeCounts" in search_filter:
            assert "hasMore" in results, "'hasMore' key is missing in results"
            assert results["hasMore"] is (expected_total > limit), "'hasMore' value is incorrect"
        else:
            assert results.get("total") == expected_total, "Total count mismatch"
        assert len(results.get("items")) == expected_total if len(results.get("items")) < limit else limit
        if expected_key:
            for item in results.get("items"):
                assert item[expected_key] == expected_value


def test_search_payment_history_for_all(session):
    """Assert that the search payment history is working."""
    payment_account = factory_payment_account()
    payment_account.save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    for i in range(20):
        payment = factory_payment(payment_status_code="CREATED")
        payment.save()
        invoice = factory_invoice(payment_account)
        invoice.save()
        factory_invoice_reference(invoice.id).save()

    results = PaymentService.search_all_purchase_history(auth_account_id=auth_account_id, search_filter={})
    assert results is not None
    assert results.get("items") is not None
    # Returns only the default number if payload is empty
    assert results.get("total") == 10


def test_create_payment_report_csv(session, rest_call_mock):
    """Assert that the create payment report is working."""
    payment_account = factory_payment_account()
    payment_account.save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    for i in range(20):
        payment = factory_payment(payment_status_code="CREATED")
        payment.save()
        invoice = factory_invoice(payment_account)
        invoice.save()
        factory_invoice_reference(invoice.id).save()

    PaymentService.create_payment_report(
        auth_account_id=auth_account_id,
        search_filter={},
        content_type="text/csv",
        report_name="test",
    )
    assert True  # If no error, then good


def test_create_payment_report_pdf(session, rest_call_mock):
    """Assert that the create payment report is working."""
    payment_account = factory_payment_account()
    payment_account.save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    for i in range(20):
        payment = factory_payment(payment_status_code="CREATED")
        payment.save()
        invoice = factory_invoice(payment_account)
        invoice.save()
        factory_invoice_reference(invoice.id).save()

    PaymentService.create_payment_report(
        auth_account_id=auth_account_id,
        search_filter={},
        content_type="application/pdf",
        report_name="test",
    )
    assert True  # If no error, then good


def test_search_payment_history_with_tz(session, executor_mock):
    """Assert that the search payment history is working."""
    payment_account = factory_payment_account()
    invoice_created_on = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    invoice_created_on = invoice_created_on.astimezone(pytz.utc)
    payment = factory_payment(payment_status_code="CREATED")
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account, created_on=invoice_created_on)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = PaymentService.search_purchase_history(auth_account_id=auth_account_id, search_filter={}, limit=1, page=1)
    assert results is not None
    assert results.get("items") is not None
    assert results.get("total") == 1

    # Add one more payment
    invoice_created_on = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    invoice_created_on = invoice_created_on.astimezone(pytz.utc)
    payment = factory_payment(payment_status_code="CREATED")
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account, created_on=invoice_created_on)
    invoice.save()
    factory_invoice_reference(invoice.id).save()

    results = PaymentService.search_purchase_history(auth_account_id=auth_account_id, search_filter={}, limit=1, page=1)
    assert results is not None
    assert results.get("items") is not None
    assert results.get("total") == 2


def test_search_account_payments(session):
    """Assert that the search account payments is working."""
    inv_number = "REG00001"
    payment_account = factory_payment_account().save()

    invoice_1 = factory_invoice(payment_account)
    invoice_1.save()
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number).save()

    payment_1 = factory_payment(
        payment_status_code="CREATED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number,
        payment_method_code=PaymentMethod.PAD.value,
    )
    payment_1.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = PaymentService.search_account_payments(auth_account_id=auth_account_id, status=None, limit=1, page=1)
    assert results is not None
    assert results.get("items") is not None
    assert results.get("total") == 1


def test_search_account_failed_payments(session):
    """Assert that the search account payments is working."""
    inv_number_1 = "REG00001"
    payment_account = factory_payment_account().save()

    invoice_1 = factory_invoice(payment_account)
    invoice_1.save()
    inv_ref_1 = factory_invoice_reference(invoice_1.id, invoice_number=inv_number_1).save()

    payment_1 = factory_payment(
        payment_status_code="FAILED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_1,
        payment_method_code=PaymentMethod.PAD.value,
    )
    payment_1.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = PaymentService.search_account_payments(auth_account_id=auth_account_id, status="FAILED", limit=1, page=1)
    assert results.get("items")
    assert results.get("total") == 1

    # Create one more payment with failed status.
    inv_number_2 = "REG00002"
    invoice_2 = factory_invoice(payment_account)
    invoice_2.save()
    inv_ref_2 = factory_invoice_reference(invoice_2.id, invoice_number=inv_number_2).save()

    payment_2 = factory_payment(
        payment_status_code="FAILED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_2,
        payment_method_code=PaymentMethod.PAD.value,
    )
    payment_2.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = PaymentService.search_account_payments(auth_account_id=auth_account_id, status="FAILED", limit=1, page=1)
    assert results.get("items")
    assert results.get("total") == 2

    # Now combine both payments into one, by setting status to invoice reference. - NSF payments
    inv_ref_1.status_code = InvoiceReferenceStatus.CANCELLED.value
    inv_ref_2.status_code = InvoiceReferenceStatus.CANCELLED.value
    inv_ref_1.save()
    inv_ref_2.save()

    # Now create new invoice reference for consolidated invoice
    inv_number_3 = "REG00003"
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number_3).save()
    factory_invoice_reference(invoice_2.id, invoice_number=inv_number_3).save()
    results = PaymentService.search_account_payments(auth_account_id=auth_account_id, status="FAILED", limit=1, page=1)
    # Now there are no active failed payments, so it should return zero records
    assert not results.get("items")
    assert results.get("total") == 0


def test_create_account_payments_for_one_failed_payment(session):
    """Assert that the create account payments is working."""
    inv_number_1 = "REG00001"
    payment_account = factory_payment_account().save()
    invoice_1 = factory_invoice(payment_account)
    invoice_1.save()
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number_1).save()
    payment_1 = factory_payment(
        payment_status_code="FAILED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_1,
        payment_method_code=PaymentMethod.PAD.value,
    )
    payment_1.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = PaymentService.search_account_payments(auth_account_id=auth_account_id, status="FAILED", limit=1, page=1)
    assert results.get("total") == 1

    new_payment = PaymentService.create_account_payment(auth_account_id=auth_account_id, is_retry_payment=True)
    old_payment = PaymentService.find_by_id(payment_1.id)
    # Assert new payment invoice number is same as old payment as there is only one failed payment.
    assert new_payment.invoice_number == old_payment.invoice_number


def test_create_account_payments_for_multiple_failed_payments(session):
    """Assert that the create account payments is working."""
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

    # Create one more payment with failed status.
    inv_number_2 = "REG00002"
    invoice_2 = factory_invoice(payment_account, total=100)
    invoice_2.save()
    factory_payment_line_item(invoice_id=invoice_2.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_2.id, invoice_number=inv_number_2).save()

    payment_2 = factory_payment(
        payment_status_code="FAILED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_2,
        invoice_amount=100,
        payment_method_code=PaymentMethod.PAD.value,
    )
    payment_2.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = PaymentService.search_account_payments(auth_account_id=auth_account_id, status="FAILED", limit=10, page=1)
    assert results.get("total") == 2

    new_payment = PaymentService.create_account_payment(auth_account_id=auth_account_id, is_retry_payment=True)
    payment_1 = PaymentService.find_by_id(payment_1.id)
    payment_2 = PaymentService.find_by_id(payment_2.id)
    # Assert new payment invoice number is different from old payment as there are more than one failed payments.
    assert new_payment.invoice_number != payment_1.invoice_number
    assert new_payment.invoice_number != payment_2.invoice_number
    assert payment_1.cons_inv_number == new_payment.invoice_number
    assert payment_2.cons_inv_number == new_payment.invoice_number
    assert new_payment.invoice_amount == payment_1.invoice_amount + payment_2.invoice_amount


def test_create_account_payments_after_consolidation(session):
    """Assert creating account payments after consolidation yields same payment record."""
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

    # Create one more payment with failed status.
    inv_number_2 = "REG00002"
    invoice_2 = factory_invoice(payment_account, total=100)
    invoice_2.save()
    factory_payment_line_item(invoice_id=invoice_2.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_2.id, invoice_number=inv_number_2).save()
    payment_2 = factory_payment(
        payment_status_code="FAILED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_2,
        invoice_amount=100,
        payment_method_code=PaymentMethod.PAD.value,
    )
    payment_2.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = PaymentService.search_account_payments(auth_account_id=auth_account_id, status="FAILED", limit=10, page=1)
    assert results.get("total") == 2

    new_payment_1 = PaymentService.create_account_payment(auth_account_id=auth_account_id, is_retry_payment=True)
    # Create account payment again and assert both payments returns same.
    new_payment_2 = PaymentService.create_account_payment(auth_account_id=auth_account_id, is_retry_payment=True)

    assert new_payment_1.id == new_payment_2.id


def test_failed_payment_after_consolidation(session):
    """Assert creating account payments after consolidation works."""
    # Create 2 failed payments, consolidate it, and then again create another failed payment.
    # Consolidate it and make sure amount matches.
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

    # Create one more payment with failed status.
    inv_number_2 = "REG00002"
    invoice_2 = factory_invoice(payment_account, total=100)
    invoice_2.save()
    factory_payment_line_item(invoice_id=invoice_2.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_2.id, invoice_number=inv_number_2).save()
    payment_2 = factory_payment(
        payment_status_code="FAILED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_2,
        invoice_amount=100,
        payment_method_code=PaymentMethod.PAD.value,
    )
    payment_2.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = PaymentService.search_account_payments(auth_account_id=auth_account_id, status="FAILED", limit=10, page=1)
    assert results.get("total") == 2

    new_payment_1 = PaymentService.create_account_payment(auth_account_id=auth_account_id, is_retry_payment=True)

    # Create another failed payment.
    inv_number_3 = "REG00003"
    invoice_3 = factory_invoice(payment_account, total=100)
    invoice_3.save()
    factory_payment_line_item(invoice_id=invoice_3.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_3.id, invoice_number=inv_number_3).save()
    payment_3 = factory_payment(
        payment_status_code="FAILED",
        payment_account_id=payment_account.id,
        invoice_number=inv_number_3,
        invoice_amount=100,
        payment_method_code=PaymentMethod.PAD.value,
    )
    payment_3.save()

    new_payment_2 = PaymentService.create_account_payment(auth_account_id=auth_account_id, is_retry_payment=True)
    assert new_payment_1.id != new_payment_2.id
    assert (
        new_payment_2.invoice_amount == payment_1.invoice_amount + payment_2.invoice_amount + payment_3.invoice_amount
    )


def test_payment_usd(session):
    """Assert that the payment with usd is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_usd_payment(paid_usd_amount=100)
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    p = PaymentService.find_by_id(payment.id)

    assert p is not None
    assert p.id is not None
    assert p.payment_system_code is not None
    assert p.payment_method_code is not None
    assert p.payment_status_code is not None
    assert p.paid_usd_amount == 100


def test_get_invoice_totals_for_statements(session):
    """This tests the invoice totals that is used for generating the amount owing in the statements."""
    statement = factory_statement()
    payment_account = factory_payment_account().save()
    # Old flow there due = total - paid - for non EFT invoices.
    data = PaymentService.create_payment_report_details(
        [
            factory_invoice(payment_account, total=100, service_fees=50).save(),
            factory_invoice(payment_account, paid=75, total=100, service_fees=50).save(),
            # Refund on APPROVAL scenario - not paid
            factory_invoice(payment_account, paid=0, refund=10, total=10).save(),
            factory_invoice(payment_account, refund=100, paid=100, total=100, service_fees=20).save(),
        ],
        {"items": []},
    )
    totals = PaymentService.get_invoices_totals(data["items"], {"to_date": statement.to_date})
    assert totals["statutoryFees"] == 190
    assert totals["serviceFees"] == 120
    assert totals["fees"] == 310
    assert totals["paid"] == 175
    assert totals["due"] == 125

    # EFT flow
    statement.from_date = datetime.now(tz=timezone.utc)
    statement.to_date = datetime.now(tz=timezone.utc) + timedelta(days=30)
    statement.save()

    # FUTURE - Partial refunds?
    data = PaymentService.create_payment_report_details(
        [
            factory_invoice(
                payment_account, paid=0, refund=0, total=100, payment_method_code=PaymentMethod.EFT.value
            ).save(),
            factory_invoice(
                payment_account, paid=0, refund=0, total=50, payment_method_code=PaymentMethod.EFT.value
            ).save(),
            # Refund outside of range - These only get considered if PAID = 0
            factory_invoice(
                payment_account,
                paid=0,
                refund=100,
                total=100,
                payment_method_code=PaymentMethod.EFT.value,
                refund_date=statement.to_date + timedelta(days=1),
            ).save(),
            # Refund within range
            factory_invoice(
                payment_account,
                paid=0,
                refund=100,
                total=100,
                payment_method_code=PaymentMethod.EFT.value,
                refund_date=statement.to_date,
            ).save(),
            # Payment Date outside of range
            factory_invoice(
                payment_account,
                paid=100,
                total=100,
                payment_method_code=PaymentMethod.EFT.value,
                payment_date=statement.to_date + timedelta(days=1),
            ).save(),
            # Payment Date within range
            factory_invoice(
                payment_account,
                paid=100,
                total=100,
                payment_method_code=PaymentMethod.EFT.value,
                payment_date=statement.to_date,
            ).save(),
            # Payment and Refund only consider payment
            factory_invoice(
                payment_account,
                paid=100,
                refund=100,
                total=100,
                payment_method_code=PaymentMethod.EFT.value,
                payment_date=statement.to_date,
            ).save(),
        ],
        {"items": []},
    )

    totals = PaymentService.get_invoices_totals(data["items"], {"to_date": statement.to_date.strftime("%Y-%m-%d")})
    assert totals["fees"] == 650
    assert totals["paid"] == 200
    # fees - paid - refund
    assert totals["due"] == 650 - 200 - 100


def test_build_grouped_invoice_context_basic():
    """Test grouped invoices."""
    invoices = [
        {"payment_method": PaymentMethod.EFT.value, "paid": 100, "total": 200,
         "line_items": [], "details": [], "status_code": InvoiceStatus.PAID.value},
        {"payment_method": PaymentMethod.CC.value, "paid": 50, "total": 50,
         "line_items": [], "details": [], "status_code": InvoiceStatus.PAID.value},
    ]
    statement = {"amount_owing": 100, "to_date": "2024-06-01"}
    summary = {"latestStatementPaymentDate": "2024-06-01", "dueDate": "2024-06-10"}

    grouped = build_grouped_invoice_context(invoices, statement, summary)

    assert any(item["payment_method"] == PaymentMethod.EFT.value for item in grouped)
    assert any(item["payment_method"] == PaymentMethod.CC.value for item in grouped)

    eft_item = next(item for item in grouped if item["payment_method"] == PaymentMethod.EFT.value)
    assert eft_item["total_paid"] == "100.00"
    assert "transactions" in eft_item

    cc_item = next(item for item in grouped if item["payment_method"] == PaymentMethod.CC.value)
    assert cc_item["total_paid"] == "50.00"


def test_calculate_invoice_summaries():
    """Test invoice summaries."""
    invoices = [
        {"payment_method": PaymentMethod.EFT.value, "paid": 0,
         "refund": 100, "total": 100, "refund_date": "2024-06-01"},
        {"payment_method": PaymentMethod.EFT.value, "paid": 100,
         "refund": 0, "total": 100, "refund_date": None},
    ]
    statement = {"to_date": "2024-06-01"}
    summary = calculate_invoice_summaries(invoices, PaymentMethod.EFT.value, statement)
    assert summary["paid"] == "100.00"
    assert summary["due"] == "0.00"
    assert summary["total"] == "200.00"


def test_build_transaction_rows():
    """Test transaction rows."""
    invoices = [
        {
            "line_items": [{"description": "Service Fee"}],
            "details": [{"label": "Folio", "value": "123"}],
            "folio_number": "F123",
            "created_on": datetime.now().isoformat(),
            "total": 100,
            "service_fees": 10,
            "gst": 5,
            "status_code": InvoiceStatus.PAID.value
        }
    ]
    rows = build_transaction_rows(invoices)
    assert rows[0]["products"] == ["Service Fee"]
    assert rows[0]["details"][0].startswith("Folio")
    assert rows[0]["fee"] == "90.00"


def test_build_statement_context():
    """Test statement."""
    statement = {
        "from_date": "2024-06-01",
        "to_date": "2024-06-30",
        "frequency": "MONTHLY",
        "amount_owing": 123.45
    }
    ctx = build_statement_context(statement)
    assert "duration" in ctx
    assert ctx["amount_owing"] == '123.45'


def test_build_statement_summary_context():
    """Test statement summary."""
    summary = {
        "lastStatementTotal": 100,
        "lastStatementPaidAmount": 50,
        "cancelledTransactions": 10,
        "latestStatementPaymentDate": "2024-06-01",
        "dueDate": "2024-06-10"
    }
    ctx = build_statement_summary_context(summary)
    assert ctx["lastStatementTotal"] == '100.00'
    assert ctx["lastStatementPaidAmount"] == '50.00'
    assert ctx["cancelledTransactions"] == '10.00'
    assert "latestStatementPaymentDate" in ctx
    assert "dueDate" in ctx
