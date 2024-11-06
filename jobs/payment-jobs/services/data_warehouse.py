# Copyright © 2022 Province of British Columbia
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
"""Create data warehouse connection.

These will get initialized by the application.
"""

# services/data_warehouse.py

from dataclasses import dataclass

import pg8000
from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


@dataclass
class DBConfig:
    """Database configuration settings."""

    database: str
    user: str
    password: str
    unix_sock: str = None
    host: str = None  # Optional for TCP connection
    port: int = 5432  # Optional with default for PostgreSQL


def getconn(connector: Connector, db_config: DBConfig) -> object:
    """Create a database connection.

    Args:
        connector (Connector): The Google Cloud SQL connector instance.
        db_config (DBConfig): The database configuration.

    Returns:
        object: A connection object to the database.
    """
    if db_config.unix_sock:
        # Use Unix socket connection with the Connector for deployment
        instance_connection_string = db_config.unix_sock.replace("/cloudsql/", "")
        return connector.connect(
            instance_connection_string=instance_connection_string,
            ip_type="public",
            user=db_config.user,
            password=db_config.password,
            db=db_config.database,
            driver="pg8000",
        )
    else:
        conn = pg8000.connect(
            database=db_config.database,
            user=db_config.user,
            password=db_config.password,
            host=db_config.host,
            port=db_config.port,
        )
        return conn


class DataWarehouseDB:
    """Data Warehouse database connection object for re-use in application."""

    def __init__(self, app=None):
        """Initialize app context on instantiation."""
        self.connector = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the app with the Data Warehouse engine and session."""
        self.connector = Connector(refresh_strategy="lazy")

        db_config = DBConfig(
            unix_sock=app.config.get("DW_UNIX_SOCKET"),
            host=app.config.get("DW_HOST"),
            port=app.config.get("DW_PORT", 5432),
            database=app.config.get("DW_NAME"),
            user=app.config.get("DW_USER"),
            password=app.config.get("DW_PASSWORD"),
        )

        self.engine = create_engine(
            "postgresql+pg8000://",
            creator=lambda: getconn(self.connector, db_config),
            pool_size=5,
            max_overflow=2,
            pool_timeout=10,
            pool_recycle=1800,
            connect_args={"use_native_uuid": False},
        )

        app.teardown_appcontext(self.teardown)

    def teardown(self, exception=None):
        """Close the connector on teardown."""
        self.connector.close()

    @property
    def session(self):
        """Provide a database session."""
        return scoped_session(sessionmaker(bind=self.engine))


data_warehouse = DataWarehouseDB()
