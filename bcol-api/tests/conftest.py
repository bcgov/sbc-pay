# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Common setup and fixtures for the py-test suite used by this service."""

import random
from unittest.mock import patch

import pytest

from bcol_api import create_app
from bcol_api import jwt as _jwt
from bcol_api import setup_jwt_manager
from tests.utilities.ldap_mock import MockLDAP


@pytest.fixture(scope="session")
def app():
    """Return a session-wide application configured in TEST mode."""
    _app = create_app("testing")

    return _app


@pytest.fixture(scope="function")
def app_request():
    """Return a session-wide application configured in TEST mode."""
    _app = create_app("testing")

    return _app


@pytest.fixture(scope="session")
def client(app):  # pylint: disable=redefined-outer-name
    """Return a session-wide Flask test client."""
    return app.test_client()


@pytest.fixture(scope="session")
def jwt(app):
    """Return session-wide jwt manager."""
    return _jwt


@pytest.fixture(scope="session")
def client_ctx(app):
    """Return session-wide Flask test client."""
    with app.test_client() as _client:
        yield _client


@pytest.fixture(scope="function")
def client_id():
    """Return a unique client_id that can be used in tests."""
    _id = random.SystemRandom().getrandbits(0x58)
    #     _id = (base64.urlsafe_b64encode(uuid.uuid4().bytes)).replace('=', '')

    return f"client-{_id}"


@pytest.fixture()
def ldap_mock():
    """Mock ldap."""
    ldap_patcher = patch("bcol_api.services.bcol_profile.ldap.initialize")
    _mock_ldap = MockLDAP()
    mock_ldap = ldap_patcher.start()
    mock_ldap.return_value = _mock_ldap
    yield
    ldap_patcher.stop()


@pytest.fixture()
def ldap_mock_error():
    """Mock ldap error."""
    ldap_patcher = patch(
        "bcol_api.services.bcol_profile.ldap.initialize",
        side_effect=Exception("Mocked Error"),
    )
    _mock_ldap = MockLDAP()
    mock_ldap = ldap_patcher.start()
    mock_ldap.return_value = _mock_ldap
    yield
    ldap_patcher.stop()


@pytest.fixture()
def query_profile_mock():
    """Mock Query Profile SOAP."""
    mock_query_profile_patcher = patch("bcol_api.services.bcol_profile.BcolProfile.get_profile_response")
    mock_query_profile = mock_query_profile_patcher.start()
    mock_query_profile.return_value = {
        "Userid": "PB25020",
        "AccountNumber": "1234567890",
        "AuthCode": "P",
        "AccountType": "B",
        "GSTStatus": " ",
        "PSTStatus": " ",
        "UserName": "Test, Test",
        "Address": {
            "AddressA": "#400A - 4000 SEYMOUR PLACE",
            "AddressB": "PENTHOUSE",
            "City": "AB1",
            "Prov": "BC",
            "Country": "CANADA",
            "PostalCode": "V8X 5J8",
        },
        "UserPhone": "(250)953-8271 EX1999",
        "UserFax": "(250)953-8212",
        "Status": "Y",
        "org-name": "BC ONLINE TECHNICAL TEAM DEVL",
        "org-type": "LAW",
        "queryProfileFlag": [{"name": "TEST"}],
    }

    yield
    mock_query_profile_patcher.stop()


@pytest.fixture()
def query_profile_contact_mock():
    """Mock Query Profile SOAP for Master user."""
    mock_query_profile_patcher = patch("bcol_api.services.bcol_profile.BcolProfile.get_profile_response")
    mock_query_profile = mock_query_profile_patcher.start()
    mock_query_profile.return_value = {
        "Userid": "PB25020",
        "AccountNumber": "1234567890",
        "AuthCode": "C",
        "AccountType": "B",
        "GSTStatus": " ",
        "PSTStatus": " ",
        "UserName": "Test, Test",
        "Address": {
            "AddressA": "#400A - 4000 SEYMOUR PLACE",
            "AddressB": "PENTHOUSE",
            "City": "AB1",
            "Prov": "BC",
            "Country": "CANADA",
            "PostalCode": "V8X 5J8",
        },
        "UserPhone": "(250)953-8271 EX1999",
        "UserFax": "(250)953-8212",
        "Status": "Y",
        "org-name": "BC ONLINE TECHNICAL TEAM DEVL",
        "org-type": "LAW",
        "queryProfileFlag": [{"name": "TEST"}],
    }

    yield
    mock_query_profile_patcher.stop()


@pytest.fixture()
def query_profile_mock_error():
    """Mock Query Profile SOAP."""
    mock_query_profile_patcher = patch(
        "bcol_api.services.bcol_profile.BcolProfile.get_profile_response",
        side_effect=Exception("Mocked Error"),
    )
    mock_query_profile_patcher.start()

    yield
    mock_query_profile_patcher.stop()


@pytest.fixture()
def payment_mock():
    """Mock Query Profile SOAP."""
    mock_payment_patcher = patch("bcol_api.services.bcol_payment.BcolPayment.debit_account")
    mock_payment = mock_payment_patcher.start()
    mock_payment.return_value = {
        "RespType": "RESPONSE",
        "ReturnCode": "0000",
        "ReturnMsg": "LOOKS OK TO ME",
        "Uniqueid": "",
        "StatFee": "-700",
        "Totamt": "-850",
        "TSFee": "-150",
        "Totgst": "+00",
        "Totpst": "+00",
        "TranID": {
            "Account": "180670",
            "UserID": "PB25020 ",
            "AppliedDate": "20191108",
            "AppliedTime": "113405428",
            "FeeCode": "BSH105  ",
            "Key": "TEST12345678901",
            "SequenceNo": "0001",
        },
    }

    yield
    mock_payment_patcher.stop()


@pytest.fixture()
def payment_mock_error():
    """Mock Payment SOAP."""
    mock_query_profile_patcher = patch(
        "bcol_api.services.bcol_payment.BcolPayment.debit_account",
        side_effect=Exception("Mocked Error"),
    )
    mock_query_profile_patcher.start()

    yield
    mock_query_profile_patcher.stop()


@pytest.fixture(scope="session", autouse=True)
def keycloak(docker_services, app):
    """Spin up a keycloak instance and initialize jwt."""
    if "USE_TEST_KEYCLOAK_DOCKER" in app.config and app.config["USE_TEST_KEYCLOAK_DOCKER"]:
        docker_services.start("keycloak")
        docker_services.wait_for_service("keycloak", 8081)

    setup_jwt_manager(app, _jwt)


@pytest.fixture(scope="session")
def docker_compose_files(pytestconfig):
    """Get the docker-compose.yml absolute path."""
    import os

    return [os.path.join(str(pytestconfig.rootdir), "tests/docker", "docker-compose.yml")]
