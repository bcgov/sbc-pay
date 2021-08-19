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

"""Tests to assure the Routing slip Service.

Test-Suite to ensure that the Routing slip Service is working as expected.
"""

from pay_api.services.fas.routing_slip import RoutingSlip as RoutingSlip_service
from pay_api.utils.enums import RoutingSlipStatus
from tests.utilities.base_test import factory_payment_account, factory_routing_slip


def test_get_links(session):
    """Assert routing slip functionalities comprehensively."""
    payment_account = factory_payment_account()
    payment_account.save()
    child_rs = factory_routing_slip(payment_account_id=payment_account.id, total=10, remaining_amount=5)
    child_rs.save()

    parent_payment_account2 = factory_payment_account()
    parent_payment_account2.save()
    parent_rs = factory_routing_slip(payment_account_id=parent_payment_account2.id, total=100, remaining_amount=50)
    parent_rs.save()

    links = RoutingSlip_service.get_links(child_rs.number)
    assert not links.get('parent', None)
    assert len(links.get('children')) == 0

    # link now

    child = RoutingSlip_service.do_link(child_rs.number, parent_rs.number)
    assert child.get('status') == RoutingSlipStatus.LINKED.value
    assert child.get('total') == child_rs.total
    assert child.get('remaining_amount') == 0

    # do a search for parent
    results = RoutingSlip_service.search({'routingSlipNumber': parent_rs.number}, page=1, limit=1)
    parent_rs_from_search = results.get('items')[0]
    assert parent_rs_from_search.get('remaining_amount') == child_rs.remaining_amount + parent_rs.remaining_amount
    assert parent_rs_from_search.get('total') == parent_rs.total
