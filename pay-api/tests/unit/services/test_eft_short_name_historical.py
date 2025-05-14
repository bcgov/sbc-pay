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

"""Tests to assure the EFT short name historical service layer.

Test-Suite to ensure that the EFT short name historical service is working as expected.
"""
from datetime import datetime

import pytest
from freezegun import freeze_time

from pay_api.models.eft_short_names_historical import EFTShortnamesHistorical as EFTShortnameHistory
from pay_api.services.eft_short_name_historical import EFTShortnameHistorical as EFTShortnameHistoryService
from pay_api.utils.enums import EFTHistoricalTypes, InvoiceStatus, PaymentMethod
from tests.utilities.base_test import (
    factory_eft_refund,
    factory_eft_shortname,
    factory_invoice,
    factory_payment_account,
)


def setup_test_data():
    """Set up test data."""
    payment_account = factory_payment_account()
    payment_account.save()

    assert payment_account.id is not None

    eft_short_name = factory_eft_shortname("TESTSHORTNAME")
    eft_short_name.save()

    return payment_account, eft_short_name


@pytest.mark.parametrize("test_transaction_date", [None, datetime(2025, 5, 1, 8, 0, 0)])
def test_create_funds_received(session, test_transaction_date):
    """Test create short name funds received history."""
    freeze_transaction_date = datetime(2024, 7, 31, 0, 0, 0)
    expected_transaction_date = test_transaction_date if test_transaction_date else freeze_transaction_date
    with freeze_time(freeze_transaction_date):
        _, short_name = setup_test_data()
        history = EFTShortnameHistory(
            short_name_id=short_name.id, amount=151.50, credit_balance=300, transaction_date=expected_transaction_date
        )
        historical_record = EFTShortnameHistoryService.create_funds_received(history)
        historical_record.save()
        assert historical_record.id is not None
        assert historical_record.amount == 151.50
        assert historical_record.created_on is not None
        assert historical_record.credit_balance == 300
        assert not historical_record.hidden
        assert not historical_record.is_processing
        assert historical_record.payment_account_id is None
        assert historical_record.related_group_link_id is None
        assert historical_record.short_name_id == short_name.id
        assert historical_record.eft_refund_id is None
        assert historical_record.invoice_id is None
        assert historical_record.statement_number is None
        assert historical_record.transaction_date.replace(microsecond=0) == expected_transaction_date
        assert historical_record.transaction_type == EFTHistoricalTypes.FUNDS_RECEIVED.value


def test_create_statement_paid(session, staff_user_mock):
    """Test create short name statement paid history."""
    transaction_date = datetime(2024, 7, 31, 0, 0, 0)
    with freeze_time(transaction_date):
        payment_account, short_name = setup_test_data()
        history = EFTShortnameHistory(
            short_name_id=short_name.id,
            amount=151.50,
            credit_balance=300,
            payment_account_id=payment_account.id,
            related_group_link_id=1,
            statement_number=1234567,
        )
        historical_record = EFTShortnameHistoryService.create_statement_paid(history)
        historical_record.save()
        assert historical_record.id is not None
        assert historical_record.amount == 151.50
        assert historical_record.created_on is not None
        assert historical_record.created_by == "STAFF USER"
        assert historical_record.credit_balance == 300
        assert not historical_record.hidden
        assert not historical_record.is_processing
        assert historical_record.payment_account_id == payment_account.id
        assert historical_record.related_group_link_id == 1
        assert historical_record.short_name_id == short_name.id
        assert historical_record.eft_refund_id is None
        assert historical_record.invoice_id is None
        assert historical_record.statement_number == 1234567
        assert historical_record.transaction_date == transaction_date
        assert historical_record.transaction_type == EFTHistoricalTypes.STATEMENT_PAID.value


def test_create_statement_reverse(session, staff_user_mock):
    """Test create short name statement reverse history."""
    transaction_date = datetime(2024, 7, 31, 0, 0, 0)
    with freeze_time(transaction_date):
        payment_account, short_name = setup_test_data()
        history = EFTShortnameHistory(
            short_name_id=short_name.id,
            amount=151.50,
            credit_balance=300,
            payment_account_id=payment_account.id,
            related_group_link_id=1,
            statement_number=1234567,
            is_processing=True,
        )
        historical_record = EFTShortnameHistoryService.create_statement_reverse(history)
        historical_record.save()
        assert historical_record.id is not None
        assert historical_record.amount == 151.50
        assert historical_record.created_on is not None
        assert historical_record.created_by == "STAFF USER"
        assert historical_record.credit_balance == 300
        assert not historical_record.hidden
        assert historical_record.is_processing
        assert historical_record.payment_account_id == payment_account.id
        assert historical_record.related_group_link_id == 1
        assert historical_record.short_name_id == short_name.id
        assert historical_record.eft_refund_id is None
        assert historical_record.invoice_id is None
        assert historical_record.statement_number == 1234567
        assert historical_record.transaction_date == transaction_date
        assert historical_record.transaction_type == EFTHistoricalTypes.STATEMENT_REVERSE.value


def test_create_invoice_refund(session, staff_user_mock):
    """Test create short name invoice refund history."""
    transaction_date = datetime(2024, 7, 31, 0, 0, 0)
    with freeze_time(transaction_date):
        payment_account, short_name = setup_test_data()
        invoice = factory_invoice(
            payment_account,
            payment_method_code=PaymentMethod.EFT.value,
            status_code=InvoiceStatus.APPROVED.value,
            total=50,
        ).save()
        history = EFTShortnameHistory(
            amount=151.50,
            credit_balance=300,
            payment_account_id=payment_account.id,
            short_name_id=short_name.id,
            invoice_id=invoice.id,
            statement_number=1234567,
            related_group_link_id=1,
        )
        historical_record = EFTShortnameHistoryService.create_invoice_refund(history)
        historical_record.save()
        assert historical_record.id is not None
        assert historical_record.amount == 151.50
        assert historical_record.created_on is not None
        assert historical_record.created_by == "STAFF USER"
        assert historical_record.credit_balance == 300
        assert not historical_record.hidden
        assert not historical_record.is_processing
        assert historical_record.payment_account_id == payment_account.id
        assert historical_record.related_group_link_id == 1
        assert historical_record.short_name_id == short_name.id
        assert historical_record.eft_refund_id is None
        assert historical_record.invoice_id == invoice.id
        assert historical_record.statement_number == 1234567
        assert historical_record.transaction_date == transaction_date
        assert historical_record.transaction_type == EFTHistoricalTypes.INVOICE_REFUND.value


def test_create_short_name_refund(session, staff_user_mock):
    """Test create short name refund history."""
    transaction_date = datetime(2024, 7, 31, 0, 0, 0)
    with freeze_time(transaction_date):
        payment_account, short_name = setup_test_data()
        eft_refund = factory_eft_refund(short_name.id, refund_amount=100).save()
        history = EFTShortnameHistory(
            amount=151.50,
            credit_balance=300,
            short_name_id=short_name.id,
            eft_refund_id=eft_refund.id,
            statement_number=1234567,
        )
        historical_record = EFTShortnameHistoryService.create_shortname_refund(history)
        historical_record.save()
        assert historical_record.id is not None
        assert historical_record.amount == 151.50
        assert historical_record.created_on is not None
        assert historical_record.created_by == "STAFF USER"
        assert historical_record.credit_balance == 300
        assert not historical_record.hidden
        assert not historical_record.is_processing
        assert historical_record.payment_account_id is None
        assert historical_record.related_group_link_id is None
        assert historical_record.short_name_id == short_name.id
        assert historical_record.statement_number is None
        assert historical_record.eft_refund_id == eft_refund.id
        assert historical_record.invoice_id is None
        assert historical_record.transaction_date == transaction_date
        assert historical_record.transaction_type == EFTHistoricalTypes.SN_REFUND_PENDING_APPROVAL.value
