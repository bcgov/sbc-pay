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

"""Tests to assure the Oauth service layer.

Test-Suite to ensure that the OAuth Service layer is working as expected.
"""
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import ConnectionError, ConnectTimeout, HTTPError

from pay_api.exceptions import ServiceUnavailableException
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import AuthHeaderType, ContentType


def test_get(app):
    """Test Get."""
    with app.app_context():
        mock_get_token = patch('pay_api.services.oauth_service.requests.Session.get')
        mock_get = mock_get_token.start()
        mock_get.return_value = Mock(status_code=201)
        mock_get.return_value.json.return_value = {}

        get_token_response = OAuthService.get('http://google.com/', '', AuthHeaderType.BEARER, ContentType.JSON)

        mock_get_token.stop()

        assert get_token_response.json() == {}


def test_post(app):
    """Test Post."""
    with app.app_context():
        mock_get_token = patch('pay_api.services.oauth_service.requests.post')
        mock_get = mock_get_token.start()
        mock_get.return_value = Mock(status_code=201)
        mock_get.return_value.json.return_value = {}

        get_token_response = OAuthService.post('http://google.com/', '', AuthHeaderType.BEARER, ContentType.JSON, {})

        mock_get_token.stop()

        assert get_token_response.json() == {}


def test_get_with_connection_errors(app):
    """Test Get with errors."""
    with app.app_context():
        mock_get_token = patch('pay_api.services.oauth_service.requests.Session.get')
        mock_get = mock_get_token.start()
        mock_get.side_effect = HTTPError()
        mock_get.return_value.json.return_value = {}
        with pytest.raises(HTTPError) as excinfo:
            OAuthService.get('http://google.com/', '', AuthHeaderType.BEARER, ContentType.JSON)
        assert excinfo.type == HTTPError
        mock_get_token.stop()

        with patch('pay_api.services.oauth_service.requests.Session.get', side_effect=ConnectionError('mocked error')):
            with pytest.raises(ServiceUnavailableException) as excinfo:
                OAuthService.get('http://google.com/', '', AuthHeaderType.BEARER, ContentType.JSON)
            assert excinfo.type == ServiceUnavailableException
        with patch('pay_api.services.oauth_service.requests.Session.get', side_effect=ConnectTimeout('mocked error')):
            with pytest.raises(ServiceUnavailableException) as excinfo:
                OAuthService.get('http://google.com/', '', AuthHeaderType.BEARER, ContentType.JSON)
            assert excinfo.type == ServiceUnavailableException


def test_post_with_connection_errors(app):
    """Test Get with errors."""
    with app.app_context():
        mock_get_token = patch('pay_api.services.oauth_service.requests.post')
        mock_get = mock_get_token.start()
        mock_get.side_effect = HTTPError()
        mock_get.return_value.json.return_value = {}
        with pytest.raises(HTTPError) as excinfo:
            OAuthService.post('http://google.com/', '', AuthHeaderType.BEARER, ContentType.JSON, {})
        assert excinfo.type == HTTPError
        mock_get_token.stop()

        with patch('pay_api.services.oauth_service.requests.post', side_effect=ConnectionError('mocked error')):
            with pytest.raises(ServiceUnavailableException) as excinfo:
                OAuthService.post('http://google.com/', '', AuthHeaderType.BEARER, ContentType.JSON, {})
            assert excinfo.type == ServiceUnavailableException
        with patch('pay_api.services.oauth_service.requests.post', side_effect=ConnectTimeout('mocked error')):
            with pytest.raises(ServiceUnavailableException) as excinfo:
                OAuthService.post('http://google.com/', '', AuthHeaderType.BEARER, ContentType.JSON, {})
            assert excinfo.type == ServiceUnavailableException
