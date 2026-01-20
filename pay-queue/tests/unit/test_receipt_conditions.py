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

"""Unit tests for receipt condition logic in payment reconciliations."""

from decimal import Decimal

import pytest

from pay_queue.enums import ReceiptMethod
from pay_queue.services.payment_reconciliations import _calculate_receipt_applied_amount


@pytest.mark.parametrize(
    "receipt_amount,receipt_method,unapplied_amount,invoices,expected_applied",
    [
        (100.0, "Online Banking Payments", 0, [], "100.0"),
        (100.0, "Online Banking Payments", 50, [], "0.0"),
        (100.0, "BCR-PAD Daily", 0, [], "0.0"),
        (100.0, "Other Method", 0, [{"amount_applied": 25.0}], "25.0"),
        (100.0, "Online Banking Payments", 0, [{"amount_applied": 25.0}], "25.0"),
        (100.0, "Online Banking Payments", 0, [{"amount_applied": 25.0}, {"amount_applied": 30.0}], "55.0"),
        (150.0, ReceiptMethod.ONLINE_BANKING.value, 0, [], "150.0"),
        (100.0, "BCR-PAD Daily", 0, [{"amount_applied": 25.0}, {"amount_applied": 30.0}, {"amount_applied": 45.0}], "100.0"),
        (100.0, ReceiptMethod.ONLINE_BANKING.value, 0, [{"amount_applied": 75.0}], "75.0"),
        (100.0, ReceiptMethod.ONLINE_BANKING.value, 25.0, [], "0.0"),
    ],
)
def test_calculate_receipt_applied_amount(receipt_amount, receipt_method, unapplied_amount, invoices, expected_applied):
    """Test the receipt applied amount calculation logic."""
    receipt = {
        "receipt_amount": receipt_amount,
        "receipt_method": receipt_method,
        "unapplied_amount": unapplied_amount,
        "invoices": invoices,
    }

    applied_amount = _calculate_receipt_applied_amount(receipt)
    assert applied_amount == Decimal(expected_applied)
