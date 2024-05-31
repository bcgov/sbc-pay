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

"""Tests to assure the Comment Service.

Test-Suite to ensure that the Comment Service is working as expected.
"""
import pytest

from pay_api.exceptions import BusinessException
from pay_api.services.fas import CommentService
from tests.utilities.base_test import factory_payment_account, factory_routing_slip


def test_create_comment(session, monkeypatch):
    """Assert create comment."""
    # create a routing slip
    # create a comment
    # retrieve all comments of a routing slip

    def token_info():  # pylint: disable=unused-argument; mocks of library methods
        return {
            'username': 'service account',
            'realm_access': {
                'roles': [
                    'system',
                    'edit'
                ]
            }
        }

    def mock_auth():  # pylint: disable=unused-argument; mocks of library methods
        return 'test'
    monkeypatch.setattr('pay_api.utils.user_context._get_token', mock_auth)
    monkeypatch.setattr('pay_api.utils.user_context._get_token_info', token_info)

    payment_account = factory_payment_account()
    payment_account.save()
    rs = factory_routing_slip(payment_account_id=payment_account.id, number='test_number')
    rs.save()

    CommentService.create(comment_value='test', rs_number=rs.number)
    result = CommentService.find_all_comments_for_a_routingslip(rs.number)

    assert result
    comments = result.get('comments')
    assert len(comments) == 1
    assert comments[0].get('routing_slip_number') == rs.number


def test_create_comment_invalid_case(session, monkeypatch):
    """Assert create comment validations."""
    # try creating a comment with invalid routing slip

    def token_info():  # pylint: disable=unused-argument; mocks of library methods
        return {
            'username': 'service account',
            'realm_access': {
                'roles': [
                    'system',
                    'edit'
                ]
            }
        }

    def mock_auth():  # pylint: disable=unused-argument; mocks of library methods
        return 'test'
    monkeypatch.setattr('pay_api.utils.user_context._get_token', mock_auth)
    monkeypatch.setattr('pay_api.utils.user_context._get_token_info', token_info)

    with pytest.raises(Exception) as exception_info:
        CommentService.create(comment_value='test', rs_number='invalid')
    assert exception_info.type == BusinessException
