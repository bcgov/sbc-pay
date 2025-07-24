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

"""Tests for RefundPartialSearch model."""
from datetime import datetime, timezone

import pytest
from _decimal import Decimal

from pay_api.models.refunds_partial import RefundPartialSearch, RefundsPartial
from pay_api.utils.enums import RefundsPartialType
from tests.utilities.base_test import (
    factory_invoice,
    factory_payment_account,
    factory_payment_line_item,
    factory_refunds_partial,
)


def test_refund_partial_search_from_row(session):
    """Test RefundPartialSearch.from_row method with all fields."""
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account).save()
    line_item = factory_payment_line_item(invoice.id, 1).save()

    refund_partial = factory_refunds_partial(
        invoice_id=invoice.id,
        payment_line_item_id=line_item.id,
        refund_amount=50.00,
        refund_type=RefundsPartialType.BASE_FEES.value,
        created_by="test_user",
        created_name="Test User",
    )

    search_model = RefundPartialSearch.from_row(refund_partial)

    assert search_model.id == refund_partial.id
    assert search_model.payment_line_item_id == line_item.id
    assert search_model.refund_type == "BASE_FEES"
    assert search_model.refund_amount == Decimal("50.00")
    assert search_model.created_by == "test_user"
    assert search_model.created_name == "Test User"
    assert isinstance(search_model.created_on, str)


def test_refund_partial_search_from_row_with_different_types(session):
    """Test RefundPartialSearch.from_row method with different refund types."""
    refund_types = [
        RefundsPartialType.BASE_FEES.value,
        RefundsPartialType.SERVICE_FEES.value,
        RefundsPartialType.FUTURE_EFFECTIVE_FEES.value,
        RefundsPartialType.PRIORITY_FEES.value,
    ]

    for i, refund_type in enumerate(refund_types):
        payment_account = factory_payment_account()
        invoice = factory_invoice(payment_account).save()
        line_item = factory_payment_line_item(invoice.id, 1).save()

        refund_partial = factory_refunds_partial(
            invoice_id=invoice.id,
            payment_line_item_id=line_item.id,
            refund_amount=10.00 + i,
            refund_type=refund_type,
            created_by=f"user_{i}",
            created_name=f"User {i}",
        )

        search_model = RefundPartialSearch.from_row(refund_partial)

        assert search_model.id == refund_partial.id
        assert search_model.payment_line_item_id == line_item.id
        assert search_model.refund_type == refund_type
        assert search_model.refund_amount == Decimal(f"{10.00 + i}")
        assert search_model.created_by == f"user_{i}"
        assert search_model.created_name == f"User {i}"


def test_refund_partial_search_from_row_with_null_values(session):
    """Test RefundPartialSearch.from_row method with null values."""
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account).save()
    line_item = factory_payment_line_item(invoice.id, 1).save()

    refund_partial = factory_refunds_partial(
        invoice_id=invoice.id,
        payment_line_item_id=line_item.id,
        refund_amount=25.50,
        refund_type=None,
        created_by="test_user",
        created_name="Test User",
        status=None,
    )

    search_model = RefundPartialSearch.from_row(refund_partial)

    assert search_model.id == refund_partial.id
    assert search_model.payment_line_item_id == line_item.id
    assert search_model.refund_type is None
    assert search_model.refund_amount == Decimal("25.50")
    assert search_model.created_by == "test_user"
    assert search_model.created_name == "Test User"


def test_refund_partial_search_from_row_with_zero_amount(session):
    """Test RefundPartialSearch.from_row method with zero refund amount."""
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account).save()
    line_item = factory_payment_line_item(invoice.id, 1).save()

    refund_partial = factory_refunds_partial(
        invoice_id=invoice.id,
        payment_line_item_id=line_item.id,
        refund_amount=0.00,
        refund_type=RefundsPartialType.BASE_FEES.value,
        created_by="test_user",
        created_name="Test User",
    )

    search_model = RefundPartialSearch.from_row(refund_partial)

    assert search_model.id == refund_partial.id
    assert search_model.payment_line_item_id == line_item.id
    assert search_model.refund_type == "BASE_FEES"
    assert search_model.refund_amount == Decimal("0.00")
    assert search_model.created_by == "test_user"
    assert search_model.created_name == "Test User"


def test_refund_partial_search_from_row_with_large_amount(session):
    """Test RefundPartialSearch.from_row method with large refund amount."""
    # Create test data
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account).save()
    line_item = factory_payment_line_item(invoice.id, 1).save()

    refund_partial = factory_refunds_partial(
        invoice_id=invoice.id,
        payment_line_item_id=line_item.id,
        refund_amount=999999.99,
        refund_type=RefundsPartialType.SERVICE_FEES.value,
        created_by="test_user",
        created_name="Test User",
    )

    search_model = RefundPartialSearch.from_row(refund_partial)

    assert search_model.id == refund_partial.id
    assert search_model.payment_line_item_id == line_item.id
    assert search_model.refund_type == "SERVICE_FEES"
    assert search_model.refund_amount == Decimal("999999.99")
    assert search_model.created_by == "test_user"
    assert search_model.created_name == "Test User"


def test_refund_partial_search_from_row_with_special_characters(session):
    """Test RefundPartialSearch.from_row method with special characters in names."""
    # Create test data
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account).save()
    line_item = factory_payment_line_item(invoice.id, 1).save()

    refund_partial = factory_refunds_partial(
        invoice_id=invoice.id,
        payment_line_item_id=line_item.id,
        refund_amount=75.25,
        refund_type=RefundsPartialType.PRIORITY_FEES.value,
        created_by="user@domain.com",
        created_name="O'Connor-Smith",
    )

    search_model = RefundPartialSearch.from_row(refund_partial)

    assert search_model.id == refund_partial.id
    assert search_model.payment_line_item_id == line_item.id
    assert search_model.refund_type == "PRIORITY_FEES"
    assert search_model.refund_amount == Decimal("75.25")
    assert search_model.created_by == "user@domain.com"
    assert search_model.created_name == "O'Connor-Smith"


def test_refund_partial_search_model_attributes():
    """Test that RefundPartialSearch model has all expected attributes."""
    # This test ensures the model structure is correct
    search_model = RefundPartialSearch(
        id=1,
        payment_line_item_id=100,
        refund_type="BASE_FEES",
        refund_amount=Decimal("50.00"),
        created_by="test_user",
        created_name="Test User",
        created_on="2024-01-01T00:00:00Z",
        is_credit=False,
    )

    assert hasattr(search_model, "id")
    assert hasattr(search_model, "payment_line_item_id")
    assert hasattr(search_model, "refund_type")
    assert hasattr(search_model, "refund_amount")
    assert hasattr(search_model, "created_by")
    assert hasattr(search_model, "created_name")
    assert hasattr(search_model, "created_on")
    assert hasattr(search_model, "is_credit")

    assert search_model.id == 1
    assert search_model.payment_line_item_id == 100
    assert search_model.refund_type == "BASE_FEES"
    assert search_model.refund_amount == Decimal("50.00")
    assert search_model.created_by == "test_user"
    assert search_model.created_name == "Test User"
    assert search_model.created_on == "2024-01-01T00:00:00Z"
    assert search_model.is_credit is False
