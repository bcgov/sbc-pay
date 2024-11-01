# Copyright © 2024 Province of British Columbia
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

"""tests/services/test_data_warehouse_connection.py."""
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from sqlalchemy import text

from services.data_warehouse import data_warehouse


@pytest.fixture
def app():
    """Create a Flask app instance configured for testing."""
    app = Flask(__name__)
    app.config['DW_HOST'] = 'mock_host'
    app.config['DW_PORT'] = 5432
    app.config['DW_NAME'] = 'mock_database'
    app.config['DW_USER'] = 'mock_user'
    app.config['DW_PASSWORD'] = 'mock_password'
    return app


@patch("services.data_warehouse.create_engine")
@patch("services.data_warehouse.Connector")
def test_data_warehouse_connection(mock_connector, mock_create_engine, app):
    """Test the connection to the Data Warehouse."""
    mock_engine = MagicMock()
    mock_connection = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_engine.connect.return_value.__enter__.return_value = mock_connection

    mock_result = [(1,)]
    mock_connection.execute.return_value.fetchone.return_value = mock_result[0]
    mock_connector.return_value.connect.return_value = mock_connection

    data_warehouse.init_app(app)

    with app.app_context():
        with data_warehouse.engine.connect() as connection:
            test_query = text("SELECT 1")
            result = connection.execute(test_query).fetchone()

            assert result is not None, "Connection to the Data Warehouse failed."
            assert result[0] == 1, "Unexpected result from the Data Warehouse connection test."

    mock_create_engine.assert_called_once()
    mock_engine.connect.assert_called_once()
    mock_connection.execute.assert_called_once_with(test_query)
