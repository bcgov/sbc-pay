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

"""Tests to assure the CFS service layer.

Test-Suite to ensure that the CFS Service layer is working as expected.
"""
from unittest.mock import patch

from requests import ConnectTimeout

from pay_api.services.cfs_service import CFSService

cfs_service = CFSService()


def test_validate_bank_account_valid(session):
    """Test create_account."""
    input_bank_details = {
        'bankInstitutionNumber': '2001',
        'bankTransitNumber': '00720',
        'bankAccountNumber': '1234567',
    }
    with patch('pay_api.services.oauth_service.requests.post') as mock_post:
        # Configure the mock to return a response with an OK status code.
        mock_post.return_value.ok = True
        mock_post.return_value.status_code = 200
        valid_address = {
            'bank_number': '0001',
            'bank_name': 'BANK OF MONTREAL',
            'branch_number': '00720',
            'transit_address': 'DATA CENTRE,PRINCE ANDREW CENTRE,,DON MILLS,ON,M3C 2H4',
            'account_number': '1234567',
            'CAS-Returned-Messages': 'VALID'
        }

        mock_post.return_value.json.return_value = valid_address

        bank_details = cfs_service.validate_bank_account(input_bank_details)
        assert bank_details.get('is_valid') is True
        assert bank_details.get('message')[0] == 'VALID'
        assert bank_details.get('status_code') == 200


def test_validate_bank_account_invalid(session):
    """Test create_account."""
    input_bank_details = {
        'bankInstitutionNumber': '2001',
        'bankTransitNumber': '00720',
        'bankAccountNumber': '1234567',
    }
    with patch('pay_api.services.oauth_service.requests.post') as mock_post:
        # Configure the mock to return a response with an OK status code.
        mock_post.return_value.ok = True
        mock_post.return_value.status_code = 400
        valid_address = {
            'bank_number': '0001',
            'bank_name': '',
            'branch_number': '00720',
            'transit_address': '',
            'account_number': '1234787%876567',
            'CAS-Returned-Messages': '0003 - Account number has invalid characters.'
                                     '0005 - Account number has non-numeric characters.'
                                     '0006 - Account number length is not valid for this bank.'
        }

        mock_post.return_value.json.return_value = valid_address

        bank_details = cfs_service.validate_bank_account(input_bank_details)
        assert bank_details.get('is_valid') is False
        assert bank_details.get('message')[0] == 'Account number has invalid characters.'
        assert bank_details.get('message')[1] == 'Account number has non-numeric characters.'
        assert bank_details.get('message')[2] == 'Account number length is not valid for this bank.'
        assert bank_details.get('status_code') == 200


def test_validate_bank_account_exception(session):
    """Test create_account."""
    input_bank_details = {
        'bankInstitutionNumber': 111,
        'bankTransitNumber': 222,
        'bankAccountNumber': 33333333
    }
    with patch('pay_api.services.oauth_service.requests.post', side_effect=ConnectTimeout('mocked error')):
        # Configure the mock to return a response with an OK status code.
        bank_details = cfs_service.validate_bank_account(input_bank_details)
        assert bank_details.get('status_code') == 503
        assert 'mocked error' in bank_details.get('message')
