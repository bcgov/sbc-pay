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
from unittest.mock import patch

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.utils.enums import CfsAccountStatus, RoutingSlipStatus

from tasks.routing_slip_task import RoutingSlipTask

from .factory import factory_routing_slip_account


def test_link_rs(session):
    """Test link routing slip."""
    child_rs_number = '1234'
    parent_rs_number = '89799'
    factory_routing_slip_account(number=child_rs_number, status=CfsAccountStatus.ACTIVE.value)
    factory_routing_slip_account(number=parent_rs_number, status=CfsAccountStatus.ACTIVE.value)
    child_rs = RoutingSlipModel.find_by_number(child_rs_number)
    parent_rs = RoutingSlipModel.find_by_number(parent_rs_number)
    # Do Link
    child_rs.status = RoutingSlipStatus.LINKED.value
    child_rs.parent_number = parent_rs.number
    child_rs.save()
    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(
        child_rs.payment_account_id)

    cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(
        payment_account.id)

    with patch('pay_api.services.CFSService.reverse_rs_receipt_in_cfs') as mock_cfs_reverse:
        with patch('pay_api.services.CFSService.create_cfs_receipt') as mock_create_cfs:
            RoutingSlipTask.link_routing_slips()
            mock_cfs_reverse.assert_called
            mock_cfs_reverse.assert_called_with(cfs_account, child_rs.number)
            mock_create_cfs.assert_called()

    # child_rs = RoutingSlipModel.find_by_number(child_rs_number)
    # parent_rs = RoutingSlipModel.find_by_number(parent_rs_number)
    # PS This has changed, no longer updating child rs payment account with parent.
    # assert child_rs.payment_account_id == parent_rs.payment_account_id
    cfs_account: CfsAccountModel = CfsAccountModel.find_by_id(cfs_account.id)
    assert cfs_account.status == CfsAccountStatus.INACTIVE.value

    # make sure next invocation doesnt fetch any records
    with patch('pay_api.services.CFSService.reverse_rs_receipt_in_cfs') as mock_cfs_reverse:
        with patch('pay_api.services.CFSService.create_cfs_receipt') as mock_create_cfs:
            RoutingSlipTask.link_routing_slips()
            mock_cfs_reverse.assert_not_called()
            mock_create_cfs.assert_not_called()
