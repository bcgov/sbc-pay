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

"""Tests to assure the CGI AP Job.

Test-Suite to ensure that the AP Refund Job is working as expected.
"""
from unittest.mock import patch

from pay_api.models import RoutingSlip
from pay_api.utils.enums import CfsAccountStatus, RoutingSlipStatus

from tasks.ap_routing_slip_refund_task import ApRoutingSlipRefundTask
from .factory import factory_refund, factory_routing_slip_account


def test_routing_slip_refunds(session, monkeypatch):
    """Test Routing slip refund job.

    Steps:
    1) Create a routing slip with remaining_amount and status REFUND_AUTHORIZED
    2) Run the job and assert status
    """
    rs_1 = 'RS0000001'
    factory_routing_slip_account(
        number=rs_1,
        status=CfsAccountStatus.ACTIVE.value,
        total=100,
        remaining_amount=0,
        auth_account_id='1234',
        routing_slip_status=RoutingSlipStatus.REFUND_AUTHORIZED.value,
        refund_amount=100)

    routing_slip = RoutingSlip.find_by_number(rs_1)
    factory_refund(routing_slip.id, {
        'name': 'TEST',
        'mailingAddress': {
            'city': 'Victoria',
            'region': 'BC',
            'street': '655 Douglas St',
            'country': 'CA',
            'postalCode': 'V8V 0B6',
            'streetAdditional': ''
        }
    })
    with patch('pysftp.Connection.put') as mock_upload:
        ApRoutingSlipRefundTask.create_ap_file()
        mock_upload.assert_called()

    routing_slip = RoutingSlip.find_by_number(rs_1)
    assert routing_slip.status == RoutingSlipStatus.REFUND_UPLOADED.value

    # Run again and assert nothing is uploaded
    with patch('pysftp.Connection.put') as mock_upload:
        ApRoutingSlipRefundTask.create_ap_file()
        mock_upload.assert_not_called()
