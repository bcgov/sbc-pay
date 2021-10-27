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

Test-Suite to ensure that the CreateAccountTask for routing slip is working as expected.
"""

from pay_api.models import CfsAccount
from pay_api.utils.enums import CfsAccountStatus
from tasks.cfs_create_account_task import CreateAccountTask

from .factory import factory_routing_slip_account


def test_create_rs_account(session):
    """Test create account."""
    # Create a pending account first, then call the job
    account = factory_routing_slip_account()
    CreateAccountTask.create_accounts()
    cfs_account: CfsAccount = CfsAccount.find_effective_by_account_id(account.id)
    assert cfs_account.status == CfsAccountStatus.ACTIVE.value
    assert cfs_account.cfs_party
    assert cfs_account.cfs_site
    assert cfs_account.cfs_account
