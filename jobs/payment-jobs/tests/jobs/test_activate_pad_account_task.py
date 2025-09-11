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

"""Tests to assure the CreateAccountTask.

Test-Suite to ensure that the CreateAccountTask is working as expected.
"""
from datetime import datetime, timedelta, timezone

from flask import current_app
from freezegun import freeze_time
from pay_api.models import CfsAccount, PaymentAccount
from pay_api.utils.enums import CfsAccountStatus, PaymentMethod

from tasks.activate_pad_account_task import ActivatePadAccountTask
from tasks.cfs_create_account_task import CreateAccountTask

from .factory import factory_create_pad_account
from .utils import valid_time_for_job


def test_activate_pad_accounts(session):
    """Test Activate PAD Accounts."""
    ActivatePadAccountTask.activate_pad_accounts()
    assert True


def test_activate_pad_accounts_with_time_check(session):
    """Test Activate account."""
    # Create a pending account first, then call the job
    account = factory_create_pad_account(auth_account_id="1")
    with freeze_time(valid_time_for_job):
        CreateAccountTask.create_accounts()
    account: PaymentAccount = PaymentAccount.find_by_id(account.id)
    cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.PAD.value)
    assert cfs_account.status == CfsAccountStatus.PENDING_PAD_ACTIVATION.value, "Created account has pending pad status"
    assert account.payment_method == PaymentMethod.PAD.value

    ActivatePadAccountTask.activate_pad_accounts()
    cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.PAD.value)
    assert (
        cfs_account.status == CfsAccountStatus.PENDING_PAD_ACTIVATION.value
    ), "Same day Job runs and shouldnt change anything."

    time_delay = current_app.config["PAD_CONFIRMATION_PERIOD_IN_DAYS"]
    with freeze_time(datetime.now(tz=timezone.utc) + timedelta(days=time_delay, minutes=1)):
        ActivatePadAccountTask.activate_pad_accounts()
        account: PaymentAccount = PaymentAccount.find_by_id(account.id)
        cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.PAD.value)
        assert (
            cfs_account.status == CfsAccountStatus.ACTIVE.value
        ), "After the confirmation period is over , status should be active"
        assert account.payment_method == PaymentMethod.PAD.value


@patch("tasks.activate_pad_account_task.ActivityLogPublisher.publish_payment_method_change_event")
def test_activate_bcol_change_to_pad(mock_publish, session):
    """Test Activate account."""
    # Create a pending account first, then call the job
    account = factory_create_pad_account(auth_account_id="1", payment_method=PaymentMethod.DRAWDOWN.value)

    with freeze_time(valid_time_for_job):
        CreateAccountTask.create_accounts()
    account = PaymentAccount.find_by_id(account.id)
    cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.PAD.value)
    assert cfs_account.status == CfsAccountStatus.PENDING_PAD_ACTIVATION.value, "Created account has pending pad status"
    assert account.payment_method == PaymentMethod.DRAWDOWN.value

    ActivatePadAccountTask.activate_pad_accounts()
    cfs_account = CfsAccount.find_effective_by_payment_method(account.id, PaymentMethod.PAD.value)
    assert (
        cfs_account.status == CfsAccountStatus.PENDING_PAD_ACTIVATION.value
    ), "Same day Job runs and shouldnt change anything."
    account = PaymentAccount.find_by_id(account.id)
    assert account.payment_method == PaymentMethod.DRAWDOWN.value

    time_delay = current_app.config["PAD_CONFIRMATION_PERIOD_IN_DAYS"]
    with freeze_time(datetime.now(tz=timezone.utc) + timedelta(days=time_delay, minutes=1)):
        ActivatePadAccountTask.activate_pad_accounts()
        assert (
            cfs_account.status == CfsAccountStatus.ACTIVE.value
        ), "After the confirmation period is over , status should be active"
        account = PaymentAccount.find_by_id(account.id)
        assert account.payment_method == PaymentMethod.PAD.value
        
        # Verify ActivityLogPublisher was called for payment method change
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args[0][0]
        assert call_args.account_id == account.auth_account_id
        assert call_args.old_method == PaymentMethod.DRAWDOWN.value
        assert call_args.new_method == PaymentMethod.PAD.value
        assert call_args.source == QueueSources.PAY_JOBS.value
