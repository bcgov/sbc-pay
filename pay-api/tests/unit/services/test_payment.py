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

import pytest
import pytz

from pay_api.models.invoice_status_code import InvoiceStatusCode
from pay_api.models.payment_account import PaymentAccount
from pay_api.services.invoice_search import InvoiceSearch
from pay_api.services.payment import Payment as PaymentService
from pay_api.services.payment import PaymentReportInput
from pay_api.services.payment_calculations import (
    build_grouped_invoice_context,
    build_statement_context,
    build_statement_summary_context,
    build_transaction_rows,
    calculate_invoice_summaries,
    determine_service_provision_status,
)
from pay_api.utils.dataclasses import PurchaseHistorySearch
from pay_api.utils.enums import ContentType, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod
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
        auth_account_id=auth_account_id, search_filter={}, content_type=ContentType.PDF.value
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

    for _i in range(20):
        payment = factory_payment(payment_status_code="CREATED")
        payment.save()
        invoice = factory_invoice(
            payment_account,
            details=[{"label": f"Label {_i}", "value": f"Value {_i}"}]
        )
        invoice.save()
        factory_invoice_reference(invoice.id).save()
        factory_payment_line_item(
            invoice_id=invoice.id,
            fee_schedule_id=1,
            description=f"Test Description {_i}"
        ).save()

    search_results = InvoiceSearch.search_all_purchase_history(
        auth_account_id=auth_account_id, search_filter={}, content_type=ContentType.CSV.value
    )
    assert search_results is not None
    assert search_results.count() == 10

    csv_data = InvoiceSearch._prepare_csv_data(search_results)
    assert csv_data is not None
    assert "columns" in csv_data
    assert "values" in csv_data
    csv_rows = csv_data["values"]
    # TRANSACTION_REPORT_DEFAULT_TOTAL is 10 in the config for tests
    assert len(csv_rows) == 10

    first_invoice = search_results.first()
    first_row = csv_rows[0]
    assert isinstance(first_row, list)
    assert len(first_row) == 16

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
    assert first_row[12] == InvoiceStatusCode.find_by_code(first_invoice.invoice_status_code).description
    assert first_row[13] == first_invoice.business_identifier
    assert first_row[14] == first_invoice.id
    assert first_row[15] == first_invoice.references[0].invoice_number

    InvoiceSearch.create_payment_report(
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


def test_build_grouped_invoice_context_basic():
    """Test grouped invoices."""
    invoices = [
        {
            "payment_method": PaymentMethod.EFT.value,
            "paid": 100,
            "total": 200,
            "line_items": [],
            "details": [],
            "status_code": InvoiceStatus.PAID.value,
        },
        {
            "payment_method": PaymentMethod.CC.value,
            "paid": 50,
            "total": 50,
            "line_items": [],
            "details": [],
            "status_code": InvoiceStatus.PAID.value,
        },
        # FUTURE - Partial refunds
        {
            "payment_method": PaymentMethod.CC.value,
            "paid": 20,
            "refund": 10,
            "total": 50,
            "line_items": [],
            "details": [],
            "status_code": InvoiceStatus.PAID.value,
        },
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
    # 50 + 20 paid, 10 refund, total 2 invoices
    assert cc_item["total_paid"] == "70.00"
    # FUTURE - Partial refunds: check due/paid/total summary
    assert "paid_summary" in cc_item
    assert "due_summary" in cc_item
    assert "totals_summary" in cc_item
    # Partial refund: paid_summary/due_summary/total_summary basic check
    assert float(cc_item["paid_summary"]) >= 0
    assert float(cc_item["totals_summary"]) >= 0


def test_calculate_invoice_summaries(session):
    """Test invoice summaries."""
    payment_account = factory_payment_account()
    payment_account.save()

    invoice1 = factory_invoice(
        payment_account,
        paid=0.00,
        refund=100.00,
        total=100.00,
        payment_method_code=PaymentMethod.EFT.value,
        refund_date="2024-06-01",
    )
    invoice1.save()

    invoice2 = factory_invoice(
        payment_account,
        paid=100.00,
        refund=0.00,
        total=100.00,
        payment_method_code=PaymentMethod.EFT.value,
        payment_date="2024-05-31",
    )
    invoice2.save()

    invoices = [
        {
            "id": invoice1.id,
            "payment_method": PaymentMethod.EFT.value,
            "paid": 0,
            "refund": 100,
            "total": 100,
            "refund_date": "2024-06-01",
        },
        {
            "id": invoice2.id,
            "payment_method": PaymentMethod.EFT.value,
            "paid": 100,
            "refund": 0,
            "total": 100,
            "refund_date": None,
        },
    ]
    statement = {"to_date": "2024-06-01"}
    summary = calculate_invoice_summaries(invoices, PaymentMethod.EFT.value, statement)
    assert summary["paid_summary"] == 100.00
    assert summary["due_summary"] == 0.00
    assert summary["totals_summary"] == 100.00


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
            "status_code": InvoiceStatus.PAID.value,
        }
    ]
    rows = build_transaction_rows(invoices)
    assert rows[0]["products"] == ["Service Fee"]
    assert rows[0]["details"][0].startswith("Folio")
    assert rows[0]["fee"] == "85.00"


def test_build_statement_context():
    """Test statement."""
    statement = {"from_date": "2024-06-01", "to_date": "2024-06-30", "frequency": "MONTHLY", "amount_owing": 123.45}
    ctx = build_statement_context(statement)
    assert "duration" in ctx
    assert ctx["amount_owing"] == "123.45"


def test_build_statement_summary_context():
    """Test statement summary."""
    summary = {
        "lastStatementTotal": 100,
        "lastStatementPaidAmount": 50,
        "cancelledTransactions": 10,
        "latestStatementPaymentDate": "2024-06-01",
        "dueDate": "2024-06-10",
    }
    ctx = build_statement_summary_context(summary)
    assert ctx["lastStatementTotal"] == "100.00"
    assert ctx["lastStatementPaidAmount"] == "50.00"
    assert ctx["cancelledTransactions"] == "10.00"
    assert "latestStatementPaymentDate" in ctx
    assert "dueDate" in ctx


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
        ("settlement scheduled", PaymentMethod.PAD.value, True),
        ("Settlement Scheduled", PaymentMethod.EFT.value, False),
        ("approved", PaymentMethod.EJV.value, True),
        ("overdue", PaymentMethod.EFT.value, True),
        ("overdue", PaymentMethod.PAD.value, False),
    ],
)
def test_determine_service_provision_status(status_code, payment_method, expected):
    """Test service provision status determination based on status and payment method."""
    assert determine_service_provision_status(status_code, payment_method) == expected


def test_generate_payment_report_template_vars_structure(session, monkeypatch):
    """Test that generate_payment_report creates correct templateVars structure."""
    payment_account = factory_payment_account().save()

    pad_invoice = factory_invoice(
        payment_account,
        status_code="SETTLEMENT_SCHED",
        payment_method_code=PaymentMethod.PAD.value,
        total=6.00,
        service_fees=1.50,
        business_identifier="SA5393",
        corp_type_code="CSO",
        created_name="PAUL ANTHONY",
        details=[{"label": "View File", "value": "VIC-S-S-251093"}],
    ).save()

    factory_payment_line_item(
        invoice_id=pad_invoice.id,
        fee_schedule_id=1,
        filing_fees=4.50,
        service_fees=1.50,
        total=6.00,
        description="View Supreme File",
    ).save()

    cc_invoice = factory_invoice(
        payment_account,
        status_code="CREATED",
        payment_method_code=PaymentMethod.CC.value,
        total=30.00,
        service_fees=0.00,
        corp_type_code="BCR",
        created_name="SYSTEM",
        details=[],
    ).save()

    factory_payment_line_item(
        invoice_id=cc_invoice.id,
        fee_schedule_id=1,
        filing_fees=30.00,
        service_fees=0.00,
        total=30.00,
        description="NSF",
    ).save()

    factory_invoice_reference(pad_invoice.id, invoice_number="REG08145451").save()
    factory_invoice_reference(cc_invoice.id, invoice_number="REG08172926").save()

    invoices = [pad_invoice, cc_invoice]
    results = {"items": []}

    for invoice in invoices:
        invoice_dict = {
            "id": invoice.id,
            "business_identifier": invoice.business_identifier,
            "corp_type_code": invoice.corp_type_code,
            "created_by": invoice.created_by,
            "created_name": invoice.created_name,
            "created_on": invoice.created_on.isoformat(),
            "paid": float(invoice.paid or 0),
            "refund": float(invoice.refund or 0),
            "status_code": invoice.invoice_status_code,
            "total": float(invoice.total),
            "gst": float(invoice.gst or 0),
            "service_fees": float(invoice.service_fees or 0),
            "payment_method": invoice.payment_method_code,
            "folio_number": invoice.folio_number,
            "details": invoice.details or [],
            "line_items": [],
        }

        for line_item in invoice.payment_line_items:
            invoice_dict["line_items"].append(
                {
                    "total": float(line_item.total),
                    "pst": float(line_item.pst or 0),
                    "statutory_fees_gst": float(line_item.statutory_fees_gst or 0),
                    "service_fees_gst": float(line_item.service_fees_gst or 0),
                    "service_fees": float(line_item.service_fees or 0),
                    "description": line_item.description,
                    "filing_type_code": "CSBSRCH" if "View" in line_item.description else "NSF",
                }
            )

        results["items"].append(invoice_dict)

    statement = {
        "from_date": "May 04, 2025",
        "to_date": "May 10, 2025",
        "is_overdue": False,
        "payment_methods": ["PAD", "CC"],
        "amount_owing": "0.00",
        "statement_total": 36.0,
        "id": 10289501,
        "frequency": "WEEKLY",
        "is_interim_statement": False,
    }

    auth_data = {"account": {"id": payment_account.auth_account_id, "name": "PAUL", "accountType": "PREMIUM"}}

    class MockUser:
        """Mock user class."""

        bearer_token = "mock_token"  # noqa: S105

    class MockResponse:
        """Mock response class."""

        def json(self):
            """Return mock contact data."""
            return {
                "contacts": [
                    {
                        "city": "Victoria",
                        "country": "CA",
                        "postalCode": "V8P2P2",
                        "region": "BC",
                        "street": "123 Main St",
                    }
                ]
            }

    monkeypatch.setattr("pay_api.services.oauth_service.OAuthService.get", lambda *args, **kwargs: MockResponse())  # noqa: ARG005

    captured_template_vars = {}

    def mock_get_report_response(request):
        """Mock report service and capture template vars."""
        captured_template_vars.update(request.template_vars)
        return "mock_report_response"

    monkeypatch.setattr("pay_api.services.report_service.ReportService.get_report_response", mock_get_report_response)

    report_inputs = PaymentReportInput(
        content_type="application/pdf",
        report_name="test-statement.pdf",
        template_name="statement_report",
        results=results,
        statement_summary=None,
    )

    response = InvoiceSearch.generate_payment_report(
        report_inputs, auth=auth_data, user=MockUser(), statement=statement
    )

    assert response == "mock_report_response"

    assert "groupedInvoices" in captured_template_vars
    assert "account" in captured_template_vars
    assert "statement" in captured_template_vars
    assert "total" in captured_template_vars

    grouped_invoices = captured_template_vars["groupedInvoices"]
    assert len(grouped_invoices) == 2  # PAD and CC

    pad_group = next(g for g in grouped_invoices if g["payment_method"] == "PAD")
    assert pad_group["total_paid"] == "0.00"
    assert len(pad_group["transactions"]) == 1
    assert "ACCOUNT STATEMENT - PRE-AUTHORIZED DEBIT" in pad_group["statement_header_text"]

    cc_group = next(g for g in grouped_invoices if g["payment_method"] == "CC")
    assert cc_group["total_paid"] == "0.00"
    assert len(cc_group["transactions"]) == 1
    assert "ACCOUNT STATEMENT - CREDIT CARD" in cc_group["statement_header_text"]

    account = captured_template_vars["account"]
    assert account["name"] == "PAUL"
    assert account["id"] == payment_account.auth_account_id
    assert "contact" in account

    statement_info = captured_template_vars["statement"]
    assert statement_info["from_date"] == "May 04, 2025"
    assert statement_info["to_date"] == "May 10, 2025"

    totals = captured_template_vars["total"]
    assert "fees" in totals
    assert "paid" in totals
    assert "due" in totals


def test_build_grouped_invoice_context_with_additional_notes():
    """Test that grouped invoice context includes additional notes based on invoice statuses."""
    invoices = [
        {
            "payment_method": PaymentMethod.PAD.value,
            "paid": 0,
            "total": 6,
            "line_items": [{"description": "View Supreme File"}],
            "details": [],
            "status_code": InvoiceStatus.SETTLEMENT_SCHEDULED.value,
        },
        {
            "payment_method": PaymentMethod.PAD.value,
            "paid": 0,
            "total": 6,
            "line_items": [{"description": "File Summary Report"}],
            "details": [],
            "status_code": InvoiceStatus.SETTLEMENT_SCHEDULED.value,
        },
        {
            "payment_method": PaymentMethod.CC.value,
            "paid": 0,
            "total": 30,
            "line_items": [{"description": "NSF"}],
            "details": [],
            "status_code": InvoiceStatus.CREATED.value,
        },
        {
            "payment_method": PaymentMethod.EFT.value,
            "paid": 100,
            "total": 100,
            "line_items": [{"description": "Business Registration"}],
            "details": [],
            "status_code": InvoiceStatus.PAID.value,
        },
        {
            "payment_method": PaymentMethod.EFT.value,
            "paid": 0,
            "total": 50,
            "line_items": [{"description": "Name Change"}],
            "details": [],
            "status_code": InvoiceStatus.CANCELLED.value,
        },
    ]

    statement = {"amount_owing": 0, "to_date": "2025-05-10"}
    statement_summary = {}

    grouped = build_grouped_invoice_context(invoices, statement, statement_summary)

    # Should have 3 payment method groups: EFT, PAD, CC (in PaymentMethod.Order)
    assert len(grouped) == 3

    eft_group = next(g for g in grouped if g["payment_method"] == PaymentMethod.EFT.value)
    pad_group = next(g for g in grouped if g["payment_method"] == PaymentMethod.PAD.value)
    cc_group = next(g for g in grouped if g["payment_method"] == PaymentMethod.CC.value)

    assert "include_service_provided" in eft_group
    assert eft_group["include_service_provided"] is True

    assert "include_service_provided" in pad_group
    assert pad_group["include_service_provided"] is True

    assert "include_service_provided" in cc_group
    assert cc_group["include_service_provided"] is False

    for group in grouped:
        assert "include_service_provided" in group
        assert isinstance(group["include_service_provided"], bool)

        for transaction in group["transactions"]:
            assert "service_provided" in transaction
            assert isinstance(transaction["service_provided"], bool)


def test_build_transaction_rows_includes_service_provided():
    """Test that build_transaction_rows includes service_provided for each transaction."""
    invoices = [
        {
            "status_code": InvoiceStatus.PAID.value,
            "line_items": [{"description": "Service 1"}],
            "details": [],
            "folio_number": "F001",
            "created_on": "2025-05-07T00:00:00",
            "total": 100,
            "service_fees": 10,
            "gst": 5,
        },
        {
            "status_code": InvoiceStatus.CANCELLED.value,
            "line_items": [{"description": "Service 2"}],
            "details": [],
            "folio_number": "F002",
            "created_on": "2025-05-08T00:00:00",
            "total": 50,
            "service_fees": 5,
            "gst": 2.5,
        },
    ]

    transactions = build_transaction_rows(invoices, PaymentMethod.PAD.value)

    assert len(transactions) == 2

    assert transactions[0]["service_provided"] is True
    assert "Service 1" in transactions[0]["products"][0]

    assert transactions[1]["service_provided"] is True
    assert "(Cancelled) Service 2" in transactions[1]["products"][0]
