# Copyright © 2026 Province of British Columbia
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

"""Unit tests for the CFS account lookup in payment reconciliations."""

from datetime import UTC, datetime

import pytest

from pay_api.models import CfsAccount, PaymentAccount
from pay_api.utils.enums import CfsAccountStatus, PaymentMethod, PaymentStatus
from pay_queue.services.payment_reconciliations import (
    _get_payment_account,
    _get_payment_by_inv_number_and_status,
    _save_payment,
)

CFS_ACCOUNT_NUMBER = "4101"
INVOICE_NUMBER = "REGT00000001"
SOURCE_TXN_NUMBER = "12345678"


def _row(account_number: str) -> dict[str, str]:
    """Build a settlement row the way _build_source_txns does - lower cased keys."""
    return {
        "record type": "PADP",
        "source transaction number": SOURCE_TXN_NUMBER,
        "target transaction number": INVOICE_NUMBER,
        "customer account": account_number,
    }


def _create_account(status: str, account_number: str = CFS_ACCOUNT_NUMBER) -> PaymentAccount:
    """Create a payment account with a single CFS account in the given status."""
    account = PaymentAccount(
        auth_account_id="1234",
        payment_method=PaymentMethod.PAD.value,
        name="Test 1234",
    ).save()
    CfsAccount(
        status=status,
        account_id=account.id,
        cfs_party="11111",
        cfs_account=account_number,
        cfs_site="29921",
        payment_method=PaymentMethod.PAD.value,
    ).save()
    return account


def _save_payment_for(account_number: str):
    """Call _save_payment for a settlement row pointing at the given CFS account."""
    _save_payment(
        datetime.now(tz=UTC),
        INVOICE_NUMBER,
        10,
        10,
        _row(account_number),
        PaymentStatus.COMPLETED.value,
        PaymentMethod.PAD.value,
        SOURCE_TXN_NUMBER,
    )


@pytest.mark.parametrize(
    "status",
    [
        CfsAccountStatus.ACTIVE.value,
        CfsAccountStatus.FREEZE.value,
        CfsAccountStatus.INACTIVE.value,
    ],
)
def test_lookup_returns_account_for_matchable_status(session, status):
    """Assert the lookup accepts every status a settled invoice can legitimately be in."""
    account = _create_account(status)

    assert _get_payment_account(_row(CFS_ACCOUNT_NUMBER)).id == account.id


@pytest.mark.parametrize(
    "status",
    [
        CfsAccountStatus.PENDING.value,
        CfsAccountStatus.PENDING_PAD_ACTIVATION.value,
    ],
)
def test_lookup_returns_none_for_transient_status(session, status):
    """Assert a transient status does not match.

    This is the real-world trigger - an account sitting in PENDING_PAD_ACTIVATION when the
    settlement file is processed, which self-heals once the activation job runs.
    """
    _create_account(status)

    assert _get_payment_account(_row(CFS_ACCOUNT_NUMBER)) is None


def test_save_payment_raises_naming_the_row(session):
    """Assert the error identifies the row, rather than surfacing as an AttributeError.

    _save_payment runs inside the try/except that builds the reconciliation failure email,
    so whatever is raised here is what lands in that email.
    """
    _create_account(CfsAccountStatus.ACTIVE.value)

    with pytest.raises(Exception) as excinfo:
        _save_payment_for("999999")

    message = str(excinfo.value)
    assert "999999" in message
    assert "PADP" in message
    assert SOURCE_TXN_NUMBER in message
    assert INVOICE_NUMBER in message
    # The likely cause is spelled out, so the alert email is actionable on its own.
    assert "PENDING_PAD_ACTIVATION" in message


def test_save_payment_skips_in_test_environments(session, app, monkeypatch):
    """Assert SKIP_EXCEPTION_FOR_TEST_ENVIRONMENT keeps the old lenient behaviour."""
    monkeypatch.setitem(app.config, "SKIP_EXCEPTION_FOR_TEST_ENVIRONMENT", True)

    _save_payment_for("999999")
    session.commit()

    assert _get_payment_by_inv_number_and_status(INVOICE_NUMBER, PaymentStatus.COMPLETED.value) is None


def test_save_payment_creates_record_when_account_matches(session):
    """Assert the happy path still writes a payment row."""
    account = _create_account(CfsAccountStatus.ACTIVE.value)

    _save_payment_for(CFS_ACCOUNT_NUMBER)
    session.commit()

    payment = _get_payment_by_inv_number_and_status(INVOICE_NUMBER, PaymentStatus.COMPLETED.value)
    assert payment is not None
    assert payment.payment_account_id == account.id
