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

from datetime import UTC, datetime, timedelta

from pay_api.services.refund import RefundModel
import pytest
import pytz

from pay_api.models.payment_account import PaymentAccount
from pay_api.services.csv_service import CsvService
from pay_api.services.invoice_search import InvoiceSearch
from pay_api.services.payment import Payment as PaymentService
from pay_api.utils.dataclasses import PurchaseHistorySearch
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, RefundStatus, RefundType
from pay_api.utils.statement_dtos import (
    GroupedInvoicesDTO,
    PaymentMethodSummaryDTO,
    PaymentMethodSummaryRawDTO,
    StatementContextDTO,
    StatementSummaryDTO,
    StatementTransactionDTO,
)
from pay_api.utils.util import current_local_time
from tests.utilities.base_test import (
    factory_applied_credits,
    factory_credit,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
    factory_refunds_partial,
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
                    "createdFrom": datetime.now(tz=UTC).strftime("%m/%d/%Y"),
                    "createdTo": datetime.now(tz=UTC).strftime("%m/%d/%Y"),
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
        results = InvoiceSearch.search_purchase_history(
            PurchaseHistorySearch(
                auth_account_id=auth_account_id,
                search_filter=search_filter,
                limit=limit,
                page=1,
                return_all=return_all,
            )
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
        if return_all:
            return
        results = InvoiceSearch.search_purchase_history(
            PurchaseHistorySearch(
                auth_account_id=auth_account_id,
                search_filter=search_filter,
                limit=limit,
                page=2,
                return_all=return_all,
            )
        )
        assert results is not None
        assert len(results.get("items")) == max(expected_total - limit, 0)
        if expected_key:
            for item in results.get("items"):
                assert item[expected_key] == expected_value


def test_search_payment_history_for_all(session):
    """Assert that the search payment history is working."""
    payment_account = factory_payment_account()
    payment_account.save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    for _i in range(20):
        payment = factory_payment(payment_status_code="CREATED")
        payment.save()
        invoice = factory_invoice(payment_account)
        invoice.save()
        factory_invoice_reference(invoice.id).save()

    results = InvoiceSearch.search_all_purchase_history(
        auth_account_id=auth_account_id, search_filter={}, query_only=False
    )
    assert results is not None
    assert results.get("items") is not None
    # Returns only the default number if payload is empty
    assert results.get("total") == 10


def test_create_payment_report_csv(session):
    """Assert that the create payment report is working."""
    payment_account = factory_payment_account()
    payment_account.save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    nsf_invoice_id = None
    for _i in range(20):
        payment = factory_payment(payment_status_code="CREATED")
        payment.save()
        payment_method = PaymentMethod.PAD.value if _i == 19 else PaymentMethod.DIRECT_PAY.value
        status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value if _i == 19 else InvoiceStatus.CREATED.value
        invoice = factory_invoice(
            payment_account,
            details=[{"label": f"Label {_i}", "value": f"Value {_i}"}],
            payment_method_code=payment_method,
            status_code=status_code,
        )
        invoice.save()
        if _i == 19:
            nsf_invoice_id = invoice.id
        factory_invoice_reference(invoice.id).save()
        factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=1, description=f"Test Description {_i}").save()

    search_results = InvoiceSearch.search_all_purchase_history(
        auth_account_id=auth_account_id, search_filter={}, query_only=True
    )
    assert search_results is not None
    assert search_results.count() == 10

    csv_data = CsvService.prepare_csv_data(search_results)
    assert csv_data is not None
    assert "columns" in csv_data
    assert "values" in csv_data
    csv_rows = csv_data["values"]
    # TRANSACTION_REPORT_DEFAULT_TOTAL is 10 in the config for tests
    assert len(csv_rows) == 10

    first_row = csv_rows[0]
    assert isinstance(first_row, list)
    assert len(first_row) == 19

    # Find the invoice from search_results that matches the CSV row's invoice ID
    csv_invoice_id = first_row[14]  # Invoice ID is at index 14
    first_invoice = next((inv for inv in search_results if inv.id == csv_invoice_id), None)
    assert first_invoice is not None, f"Invoice with ID {csv_invoice_id} not found in search results"

    assert first_row[0] == first_invoice.corp_type.product
    assert first_row[1] == first_invoice.corp_type.code
    expected_filing_type_codes = ",".join(
        [pli.fee_schedule.filing_type_code for pli in first_invoice.payment_line_items if pli.fee_schedule]
    )
    assert first_row[2] == expected_filing_type_codes
    expected_descriptions = ",".join([pli.description for pli in first_invoice.payment_line_items])
    assert first_row[3] == expected_descriptions
    expected_details = ",".join([f"{detail.get('label')} {detail.get('value')}" for detail in first_invoice.details])
    assert first_row[4] == expected_details
    assert first_row[5] == first_invoice.folio_number
    assert first_row[6] == first_invoice.created_name
    assert isinstance(first_row[7], str) and "Pacific Time" in first_row[7]
    expected_total = float(first_invoice.total)
    expected_service_fee = float(first_invoice.service_fees)
    assert float(first_row[8]) == expected_total
    assert float(first_row[10]) == expected_total - expected_service_fee
    assert float(first_row[11]) == expected_service_fee
    assert first_row[12] == "Non Sufficient Funds"
    assert first_invoice.id == nsf_invoice_id
    assert first_invoice.payment_method_code == PaymentMethod.PAD.value
    assert first_invoice.invoice_status_code == InvoiceStatus.SETTLEMENT_SCHEDULED.value
    assert first_row[13] == first_invoice.business_identifier
    assert first_row[14] == first_invoice.id
    assert first_row[15] == first_invoice.references[0].invoice_number
    assert first_row[16] == 0
    assert first_row[17] == 0
    assert first_row[18] == 0

    InvoiceSearch.create_payment_report(
        auth_account_id=auth_account_id,
        search_filter={},
        content_type="text/csv",
        report_name="test",
    )
    assert True  # If no error, then good


def test_csv_service_create_report(session):
    """Assert that the CSV service creates a streaming CSV report correctly."""
    payment_account = factory_payment_account()
    payment_account.save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    invoice = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.CC.value,
        status_code=InvoiceStatus.CREATED.value,
        details=[{"label": "Test Label", "value": "Test Value"}],
    )
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=1, description="Test Description").save()

    search_results = InvoiceSearch.search_all_purchase_history(
        auth_account_id=auth_account_id, search_filter={}, query_only=True
    )

    csv_data = CsvService.prepare_csv_data(search_results)
    assert csv_data is not None
    assert "columns" in csv_data
    assert "values" in csv_data

    csv_report = CsvService.create_report(csv_data)
    assert csv_report is not None

    csv_content = b"".join(csv_report)
    assert csv_content is not None
    assert len(csv_content) > 0

    csv_lines = csv_content.decode("utf-8").split("\n")
    assert len(csv_lines) > 1

    header_line = csv_lines[0]
    assert "Product" in header_line
    assert "Status" in header_line
    assert "Transaction Details" in header_line
    assert "Refund" in header_line
    assert "Applied Credits" in header_line
    assert "Account Credits" in header_line

    data_lines = [line for line in csv_lines[1:] if line.strip()]
    assert len(data_lines) >= 1


def test_create_payment_report_pdf(session, rest_call_mock):
    """Assert that the create payment report is working."""
    payment_account = factory_payment_account()
    payment_account.save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    for _i in range(20):
        payment = factory_payment(payment_status_code="CREATED")
        payment.save()
        invoice = factory_invoice(payment_account)
        invoice.save()
        factory_invoice_reference(invoice.id).save()

    InvoiceSearch.create_payment_report(
        auth_account_id=auth_account_id,
        search_filter={},
        content_type="application/pdf",
        report_name="test",
    )
    assert True  # If no error, then good


def test_csv_report_with_refunds_and_credits(session):
    """Assert that CSV report correctly displays partial refunds, partial credits, applied credits, and account credits."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.PAD.value)
    payment_account.save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    invoice1 = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.DIRECT_PAY.value,
        status_code=InvoiceStatus.PAID.value,
        total=100.00,
        paid=100.00,
        refund=30.00,
    )
    invoice1.save()
    invoice1.refund_date = datetime.now(tz=UTC)
    invoice1.save()
    factory_invoice_reference(invoice1.id).save()
    line_item1 = factory_payment_line_item(invoice_id=invoice1.id, fee_schedule_id=1)
    line_item1.save()
    refund1 = RefundModel(
        invoice_id=invoice1.id,
        type=RefundType.INVOICE.value,
        status=RefundStatus.APPROVED.value,
        requested_date=datetime.now(tz=UTC),
    ).save()
    partial_refund1 = factory_refunds_partial(
        invoice_id=invoice1.id,
        payment_line_item_id=line_item1.id,
        refund_amount=30.00,
        is_credit=False,
    )
    partial_refund1.refund_id = refund1.id
    partial_refund1.save()

    invoice2 = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.PAD.value,
        status_code=InvoiceStatus.PAID.value,
        total=100.00,
        paid=100.00,
        refund=25.00,
    )
    invoice2.save()
    invoice2.refund_date = datetime.now(tz=UTC)
    invoice2.save()
    factory_invoice_reference(invoice2.id).save()
    line_item2 = factory_payment_line_item(invoice_id=invoice2.id, fee_schedule_id=1)
    line_item2.save()

    refund2 = RefundModel(
        invoice_id=invoice2.id,
        type=RefundType.INVOICE.value,
        status=RefundStatus.APPROVED.value,
        requested_date=datetime.now(tz=UTC),
    ).save()

    partial_refund2 = factory_refunds_partial(
        invoice_id=invoice2.id,
        payment_line_item_id=line_item2.id,
        refund_amount=25.00,
        is_credit=True,
    )
    partial_refund2.refund_id = refund2.id
    partial_refund2.save()

    credit = factory_credit(account_id=payment_account.id, amount=50.00)
    factory_applied_credits(invoice_id=invoice2.id, credit_id=credit.id, amount_applied=20.00)

    factory_credit(account_id=payment_account.id, amount=100.00, created_invoice_id=invoice2.id)

    search_results = InvoiceSearch.search_all_purchase_history(
        auth_account_id=auth_account_id, search_filter={}, query_only=True
    )
    csv_data = CsvService.prepare_csv_data(search_results)

    assert csv_data is not None
    assert "columns" in csv_data
    assert "values" in csv_data

    csv_rows = csv_data["values"]
    assert len(csv_rows) == 2

    rows_by_invoice_id = {row[14]: row for row in csv_rows}

    row1 = rows_by_invoice_id[invoice1.id]
    assert row1[12] == "Partially Refunded"
    assert float(row1[16]) == -30.00
    assert float(row1[17]) == 0
    assert float(row1[18]) == 0

    row2 = rows_by_invoice_id[invoice2.id]
    assert row2[12] == "Partially Credited"
    assert float(row2[16]) == -25.00
    assert float(row2[17]) == 20.00
    assert float(row2[18]) == -100.00


def test_search_payment_history_with_tz(session, executor_mock):
    """Assert that the search payment history is working."""
    payment_account = factory_payment_account()
    invoice_created_on = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    invoice_created_on = invoice_created_on.astimezone(pytz.utc)
    payment = factory_payment(payment_status_code="CREATED")
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account, created_on=invoice_created_on)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = InvoiceSearch.search_purchase_history(
        PurchaseHistorySearch(auth_account_id=auth_account_id, search_filter={}, limit=1, page=1)
    )
    assert results is not None
    assert results.get("items") is not None
    assert results.get("total") == 1

    # Add one more payment
    invoice_created_on = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    invoice_created_on = invoice_created_on.astimezone(pytz.utc)
    payment = factory_payment(payment_status_code="CREATED")
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account, created_on=invoice_created_on)
    invoice.save()
    factory_invoice_reference(invoice.id).save()

    results = InvoiceSearch.search_purchase_history(
        PurchaseHistorySearch(auth_account_id=auth_account_id, search_filter={}, limit=1, page=1)
    )
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
    data = InvoiceSearch.create_payment_report_details(
        [
            factory_invoice(payment_account, total=100, service_fees=50).save(),
            factory_invoice(payment_account, paid=75, total=100, service_fees=50).save(),
            # Refund on APPROVAL scenario - not paid
            factory_invoice(payment_account, paid=0, refund=10, total=10).save(),
            factory_invoice(payment_account, refund=100, paid=100, total=100, service_fees=20).save(),
        ],
        {"items": []},
    )
    totals = InvoiceSearch.get_invoices_totals(data["items"], {"to_date": statement.to_date})
    assert totals["statutoryFees"] == 190
    assert totals["serviceFees"] == 120
    assert totals["fees"] == 310
    assert totals["paid"] == 175
    assert totals["due"] == 125

    # EFT flow
    statement.from_date = datetime.now(tz=UTC)
    statement.to_date = datetime.now(tz=UTC) + timedelta(days=30)
    statement.save()

    # FUTURE - Partial refunds?
    data = InvoiceSearch.create_payment_report_details(
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

    totals = InvoiceSearch.get_invoices_totals(data["items"], {"to_date": statement.to_date.strftime("%Y-%m-%d")})
    assert totals["fees"] == 650
    assert totals["paid"] == 200
    # fees - paid - refund
    assert totals["due"] == 650 - 200 - 100


def test_statement_transaction_dto_from_orm(session):
    """Test StatementTransactionDTO.from_orm creates correct DTO."""
    payment_account = factory_payment_account()
    payment_account.save()

    invoice = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=100,
        service_fees=10,
        paid=0,
    )
    invoice.save()
    factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=1).save()

    statement_to_date = datetime.now(tz=UTC)
    dto = StatementTransactionDTO.from_orm(invoice, PaymentMethod.EFT.value, statement_to_date)

    assert dto.invoice_id == invoice.id
    assert dto.products == ["test"]
    assert dto.folio == invoice.folio_number
    assert dto.fee == 90  # 100 - 10 service_fees - 0 gst
    assert dto.service_fee == 10
    assert dto.total == 100
    assert dto.status_code == "APPROVED"
    assert dto.service_provided is True
    assert len(dto.line_items) == 1


def test_grouped_invoices_dto_from_invoices_and_summary(session):
    """Test GroupedInvoicesDTO.from_invoices_and_summary creates correct DTO."""
    payment_account = factory_payment_account()
    payment_account.save()

    invoice1 = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=100,
        paid=0,
    )
    invoice1.save()
    factory_payment_line_item(invoice_id=invoice1.id, fee_schedule_id=1).save()

    invoice2 = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.PAID.value,
        total=50,
        paid=50,
    )
    invoice2.save()
    factory_payment_line_item(invoice_id=invoice2.id, fee_schedule_id=1).save()

    db_summary = PaymentMethodSummaryRawDTO(
        totals=150,
        fees=150,
        service_fees=0,
        gst=0,
        paid=50,
        due=100,
        invoice_count=2,
        credits_applied=0,
        counted_refund=0,
    )

    statement_to_date = datetime.now(tz=UTC)
    statement = factory_statement(
        payment_account_id=payment_account.id,
        from_date=statement_to_date - timedelta(days=30),
        to_date=statement_to_date,
    )
    statement.amount_owing = 100
    statement_summary = {"dueDate": "2024-07-01"}

    dto = GroupedInvoicesDTO.from_invoices_and_summary(
        payment_method=PaymentMethod.EFT.value,
        invoices_orm=[invoice1, invoice2],
        db_summary=db_summary,
        statement=statement,
        statement_summary=statement_summary,
        statement_to_date=statement_to_date,
        is_first=True,
    )

    assert dto.payment_method == PaymentMethod.EFT.value
    assert dto.totals == 150.00
    assert dto.paid == 50.00
    assert dto.due == 100.00
    assert dto.is_index_0 is True
    assert len(dto.transactions) == 2
    assert dto.include_service_provided is True


def test_statement_context_dto_from_dict():
    """Test StatementContextDTO.from_dict creates correct DTO."""
    statement = {
        "from_date": "June 01, 2024",
        "to_date": "June 30, 2024",
        "frequency": "MONTHLY",
        "amount_owing": 123.45,
        "id": 1,
        "is_interim_statement": False,
    }

    dto = StatementContextDTO.from_dict(statement)

    assert dto.duration == "June 01, 2024 - June 30, 2024"
    assert dto.amount_owing == 123.45
    assert dto.frequency == "MONTHLY"
    assert dto.id == 1
    assert dto.is_interim_statement is False


def test_statement_summary_dto_from_dict():
    """Test StatementSummaryDTO.from_dict creates correct DTO."""
    summary = {
        "lastStatementTotal": 100,
        "lastStatementPaidAmount": 50,
        "cancelledTransactions": 10,
        "latestStatementPaymentDate": "2024-06-01",
        "dueDate": "2024-06-10",
    }

    dto = StatementSummaryDTO.from_dict(summary)

    assert dto.last_statement_total == 100
    assert dto.last_statement_paid_amount == 50
    assert dto.cancelled_transactions == 10
    assert dto.latest_statement_payment_date is not None
    assert dto.due_date is not None


@pytest.mark.parametrize(
    "status_code,payment_method,expected",
    [
        (InvoiceStatus.PAID.value, PaymentMethod.PAD.value, True),
        (InvoiceStatus.PAID.value, PaymentMethod.CC.value, True),
        (InvoiceStatus.CANCELLED.value, PaymentMethod.PAD.value, True),
        (InvoiceStatus.CANCELLED.value, PaymentMethod.EFT.value, True),
        (InvoiceStatus.CREATED.value, PaymentMethod.CC.value, False),
        (InvoiceStatus.CREDITED.value, PaymentMethod.EJV.value, True),
        (InvoiceStatus.REFUND_REQUESTED.value, PaymentMethod.INTERNAL.value, True),
        (InvoiceStatus.REFUNDED.value, PaymentMethod.PAD.value, True),
        (InvoiceStatus.APPROVED.value, PaymentMethod.PAD.value, True),
        (InvoiceStatus.SETTLEMENT_SCHEDULED.value, PaymentMethod.PAD.value, True),
        (InvoiceStatus.APPROVED.value, PaymentMethod.EFT.value, True),
        (InvoiceStatus.OVERDUE.value, PaymentMethod.EFT.value, True),
        (InvoiceStatus.APPROVED.value, PaymentMethod.EJV.value, True),
        (InvoiceStatus.APPROVED.value, PaymentMethod.INTERNAL.value, True),
        (InvoiceStatus.DELETED.value, PaymentMethod.PAD.value, False),
        (InvoiceStatus.DELETE_ACCEPTED.value, PaymentMethod.CC.value, False),
        (InvoiceStatus.OVERDUE.value, PaymentMethod.PAD.value, False),
        (InvoiceStatus.SETTLEMENT_SCHEDULED.value, PaymentMethod.CC.value, False),
        (InvoiceStatus.PARTIAL.value, PaymentMethod.EFT.value, False),
    ],
)
def test_determine_service_provision_status(status_code, payment_method, expected):
    """Test service provision status determination based on status and payment method."""
    assert StatementTransactionDTO.determine_service_provision_status(status_code, payment_method) == expected


def test_payment_method_summary_raw_dto_from_db_row():
    """Test PaymentMethodSummaryRawDTO.from_db_row() calculates due correctly."""

    class MockRow:
        def __init__(self):
            self.totals = 500.00
            self.fees = 450.00
            self.service_fees = 25.00
            self.gst = 25.00
            self.paid = 100.00
            self.counted_refund = 0.00
            self.invoice_count = 5
            self.credits_applied = 2.00
            self.is_pre_summary = True
            self.paid_pre_balance = 98.00

    row = MockRow()
    dto = PaymentMethodSummaryRawDTO.from_db_row(row)

    assert dto.totals == 498.00
    assert dto.fees == 450.00
    assert dto.service_fees == 25.00
    assert dto.gst == 25.00
    assert dto.paid == 98.00
    assert dto.due == 400.00
    assert dto.invoice_count == 5
    assert dto.credits_applied == 2.00


def test_payment_method_summary_dto_from_db_summary():
    """Test PaymentMethodSummaryDTO.from_db_summary() formats currency correctly."""
    raw_dto = PaymentMethodSummaryRawDTO(
        totals=500.00,
        fees=450.00,
        service_fees=25.00,
        gst=25.00,
        paid=100.00,
        due=400.00,
        credits_applied=0.00,
        invoice_count=5,
        counted_refund=0,
    )

    dto = PaymentMethodSummaryDTO.from_db_summary(raw_dto)

    assert dto.totals == 500.00
    assert dto.fees == 450.00
    assert dto.service_fees == 25.00
    assert dto.gst == 25.00
    assert dto.paid == 100.00
    assert dto.due == 400.00

    dto_none = PaymentMethodSummaryDTO.from_db_summary(None)
    assert dto_none.totals == 0
    assert dto_none.fees == 0
    assert dto_none.service_fees == 0
    assert dto_none.gst == 0
    assert dto_none.paid == 0
    assert dto_none.due == 0


def test_grouped_invoices_dto_with_internal_payment_method(session):
    """Test GroupedInvoicesDTO handles INTERNAL payment method with staff payments."""
    payment_account = factory_payment_account()
    payment_account.save()

    invoice = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.INTERNAL.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=100,
        paid=0,
    )
    invoice.save()
    factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=1).save()

    db_summary = PaymentMethodSummaryRawDTO(
        totals=100,
        fees=100,
        service_fees=0,
        gst=0,
        paid=0,
        due=100,
        invoice_count=1,
        credits_applied=0,
        counted_refund=0,
    )

    statement = factory_statement(
        payment_account_id=payment_account.id,
        to_date="2024-06-01",
    )
    statement_summary = {}
    statement_to_date = datetime.now(tz=UTC)

    dto = GroupedInvoicesDTO.from_invoices_and_summary(
        payment_method=PaymentMethod.INTERNAL.value,
        invoices_orm=[invoice],
        db_summary=db_summary,
        statement=statement,
        statement_summary=statement_summary,
        statement_to_date=statement_to_date,
        is_first=True,
    )

    assert dto.payment_method == PaymentMethod.INTERNAL.value
    assert dto.is_staff_payment is True
    assert "STAFF" in dto.statement_header_text


def test_grouped_invoices_dto_with_eft_interim_statement(session):
    """Test GroupedInvoicesDTO handles EFT interim statement correctly."""
    payment_account = factory_payment_account()
    payment_account.save()

    invoice = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=100,
        paid=0,
    )
    invoice.save()
    factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=1).save()

    db_summary = PaymentMethodSummaryRawDTO(
        totals=100,
        fees=100,
        service_fees=0,
        gst=0,
        paid=0,
        due=100,
        invoice_count=1,
        credits_applied=0,
        counted_refund=0,
    )

    statement = factory_statement(
        payment_account_id=payment_account.id,
        to_date="2024-06-01",
        is_interim_statement=True,
        amount_owing=100,
    )
    statement_summary = {"latestStatementPaymentDate": "2024-05-15"}
    statement_to_date = datetime.now(tz=UTC)

    dto = GroupedInvoicesDTO.from_invoices_and_summary(
        payment_method=PaymentMethod.EFT.value,
        invoices_orm=[invoice],
        db_summary=db_summary,
        statement=statement,
        statement_summary=statement_summary,
        statement_to_date=statement_to_date,
        is_first=True,
    )

    assert dto.payment_method == PaymentMethod.EFT.value
    assert dto.amount_owing == 100
    assert dto.latest_payment_date == "2024-05-15"
    assert dto.due_date is None  # Not set for interim statements


def test_grouped_invoices_dto_with_eft_regular_statement(session):
    """Test GroupedInvoicesDTO handles EFT regular statement with due date."""
    payment_account = factory_payment_account()
    payment_account.save()

    invoice = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=100,
        paid=0,
    )
    invoice.save()
    factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=1).save()

    db_summary = PaymentMethodSummaryRawDTO(
        totals=100,
        fees=100,
        service_fees=0,
        gst=0,
        paid=0,
        due=100,
        invoice_count=1,
        credits_applied=0,
        counted_refund=0,
    )

    statement = factory_statement(
        payment_account_id=payment_account.id,
        to_date="2024-06-01",
        is_interim_statement=False,
        amount_owing=100,
    )
    statement_summary = {"dueDate": "2024-07-01"}
    statement_to_date = datetime.now(tz=UTC)

    dto = GroupedInvoicesDTO.from_invoices_and_summary(
        payment_method=PaymentMethod.EFT.value,
        invoices_orm=[invoice],
        db_summary=db_summary,
        statement=statement,
        statement_summary=statement_summary,
        statement_to_date=statement_to_date,
        is_first=True,
    )

    assert dto.payment_method == PaymentMethod.EFT.value
    assert dto.amount_owing == 100
    assert dto.latest_payment_date is None  # Not set for regular statements
    assert dto.due_date is not None  # Should be formatted date


def test_statement_transaction_dto_with_multiple_line_items(session):
    """Test StatementTransactionDTO handles multiple line items correctly."""
    payment_account = factory_payment_account()
    payment_account.save()

    invoice = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=200,
        service_fees=20,
        paid=0,
    )
    invoice.save()

    factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=1, description="Filing Fee", total=100).save()
    factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=2, description="Service Fee", total=100).save()

    statement_to_date = datetime.now(tz=UTC)
    dto = StatementTransactionDTO.from_orm(invoice, PaymentMethod.EFT.value, statement_to_date)

    assert len(dto.products) == 2
    assert "Filing Fee" in dto.products
    assert "Service Fee" in dto.products
    assert len(dto.line_items) == 2


def test_statement_context_dto_with_daily_frequency():
    """Test StatementContextDTO handles DAILY frequency correctly."""
    statement = {
        "from_date": "June 01, 2024",
        "to_date": "June 01, 2024",
        "frequency": "DAILY",
        "amount_owing": 100,
    }

    dto = StatementContextDTO.from_dict(statement)

    assert dto.duration == "June 01, 2024"
    assert dto.frequency == "DAILY"


def test_statement_summary_dto_with_zero_cancelled_transactions():
    """Test StatementSummaryDTO handles zero cancelled transactions correctly."""
    summary = {
        "lastStatementTotal": 100,
        "lastStatementPaidAmount": 50,
        "cancelledTransactions": 0,  # Should be None in output
    }

    dto = StatementSummaryDTO.from_dict(summary)

    assert dto.last_statement_total == 100
    assert dto.last_statement_paid_amount == 50
    assert dto.cancelled_transactions is None  # Zero should become None
