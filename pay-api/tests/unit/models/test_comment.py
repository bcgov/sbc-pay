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

"""Tests to assure the Comment Model Class.

Test-Suite to ensure that the Comment Model Class is working as expected.
"""
from faker import Faker

from pay_api.models import Comment as CommentModel
from tests.utilities.base_test import (
    factory_comments,
    factory_payment_account,
    factory_routing_slip,
)


fake = Faker()


def test_find_comment(session):
    """Assert a comment is stored and fetched."""
    # Create a payment account and routing slip and then a comment record

    payment_account = factory_payment_account()
    payment_account.save()
    rs = factory_routing_slip(payment_account_id=payment_account.id)
    rs.save()

    comments = factory_comments(routing_slip_number=rs.number)
    comments.save()

    fetched_comment = CommentModel.find_all_comments_for_a_routingslip(routing_slip_number=rs.number)

    assert fetched_comment
    assert fetched_comment[0].routing_slip_number == rs.number
