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

"""Tests to assure the Routing slip Class.

Test-Suite to ensure that the Roting slip Class is working as expected.
"""

from faker import Faker

from pay_api.models import RoutingSlip
from tests.utilities.base_test import factory_payment_account, factory_routing_slip, factory_routing_slip_usd

fake = Faker()


def test_routing_slip_find_creation(session):
    """Assert a routing slip is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment_account.save()

    rs = factory_routing_slip(
        payment_account_id=payment_account.id,
        contact_name="John Doe",
        street="123 Main St",
        street_additional="Suite 200",
        city="Victoria",
        region="BC",
        postal_code="V8V 3V3",
        country="CA",
        delivery_instructions="Leave at the door",
    )
    rs.save()
    assert rs.id is not None
    assert rs.contact_name == "John Doe"
    assert rs.street == "123 Main St"
    assert rs.street_additional == "Suite 200"
    assert rs.city == "Victoria"
    assert rs.region == "BC"
    assert rs.postal_code == "V8V 3V3"
    assert rs.country == "CA"
    assert rs.delivery_instructions == "Leave at the door"

    routing_slip = RoutingSlip()
    assert routing_slip.find_by_number(rs.number) is not None


def test_routing_slip_find_search(session):
    """Assert a routing slip is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment_account.save()

    rs = factory_routing_slip(number=fake.name(), payment_account_id=payment_account.id)
    rs.save()

    for _i in range(20):
        factory_routing_slip(number=fake.name(), payment_account_id=payment_account.id).save()

    routing_slip = RoutingSlip()
    search_dict = {"routingSlipNumber": rs.number}
    res, count = routing_slip.search(search_dict, page=1, limit=1, return_all=True)
    assert count == 1
    assert len(res) == 1, "searched with routing slip.so only one record"

    res, count = routing_slip.search({}, page=1, limit=1, return_all=True)
    assert count == 21
    assert len(res) == 21, "retun all true ;so shud return all records"

    res, count = routing_slip.search({}, page=1, limit=1, return_all=False)
    assert count == 1
    assert len(res) == 1, "return all false"


def test_routing_slip_usd_creation(session):
    """Assert a routing slip is stored with total_usd column.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment_account.save()

    rs = factory_routing_slip_usd(payment_account_id=payment_account.id, total_usd=50)
    rs.save()
    assert rs.id is not None
    assert rs.total_usd == 50

    routing_slip = RoutingSlip()
    assert routing_slip.find_by_number(rs.number) is not None
