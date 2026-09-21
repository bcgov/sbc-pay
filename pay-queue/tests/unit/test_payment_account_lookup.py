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

import pytest

from pay_api.models import CfsAccount, PaymentAccount
from pay_api.utils.enums import CfsAccountStatus, PaymentMethod
from pay_queue.services.payment_reconciliations import _get_payment_account

CFS_ACCOUNT_NUMBER = "4101"


def _row(account_number: str) -> dict[str, str]:
    """Build a settlement row the way _build_source_txns does - lower cased keys."""
    return {
        "record type": "BOLP",
        "source transaction number": "12345678",
        "target transaction number": "REG00000001",
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


@pytest.mark.parametrize(
    "status",
    [
        CfsAccountStatus.ACTIVE.value,
        CfsAccountStatus.FREEZE.value,
        CfsAccountStatus.INACTIVE.value,
    ],
)
def test_returns_account_for_matchable_status(session, status):
    """Assert the account is returned for every status the lookup accepts."""
    account = _create_account(status)

    assert _get_payment_account(_row(CFS_ACCOUNT_NUMBER)).id == account.id


def test_raises_naming_the_row_when_cfs_account_is_unknown(session):
    """Assert the error identifies the row, rather than surfacing as an AttributeError."""
    _create_account(CfsAccountStatus.ACTIVE.value)

    with pytest.raises(Exception) as excinfo:
        _get_payment_account(_row("999999"))

    message = str(excinfo.value)
    assert "999999" in message
    assert "BOLP" in message
    assert "12345678" in message
    assert "REG00000001" in message
    # The likely cause is spelled out, so the alert email is actionable on its own.
    assert "PENDING_PAD_ACTIVATION" in message


@pytest.mark.parametrize(
    "status",
    [
        CfsAccountStatus.PENDING.value,
        CfsAccountStatus.PENDING_PAD_ACTIVATION.value,
    ],
)
def test_raises_when_cfs_account_is_in_a_transient_status(session, status):
    """Assert a transient status fails the lookup rather than silently matching.

    This is the real-world trigger - an account sitting in PENDING_PAD_ACTIVATION when the
    settlement file is processed, which self-heals once the activation job runs.
    """
    _create_account(status)

    with pytest.raises(Exception) as excinfo:
        _get_payment_account(_row(CFS_ACCOUNT_NUMBER))

    assert CFS_ACCOUNT_NUMBER in str(excinfo.value)


def test_returns_none_instead_of_raising_in_test_environments(session, app, monkeypatch):
    """Assert SKIP_EXCEPTION_FOR_TEST_ENVIRONMENT keeps the old lenient behaviour."""
    monkeypatch.setitem(app.config, "SKIP_EXCEPTION_FOR_TEST_ENVIRONMENT", True)

    assert _get_payment_account(_row("999999")) is None
