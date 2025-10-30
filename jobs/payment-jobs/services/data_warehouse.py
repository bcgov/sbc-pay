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

from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker


@dataclass
class DBConfig:
    """Database configuration settings for IAM authentication."""

    instance_connection_name: str  # Format: "project:region:instance"
    database: str
    user: str  # IAM user email format: "user@project.iam"
    enable_iam_auth: bool = True


class DataWarehouseDB:
    """Data Warehouse connection using IAM authentication."""

    def __init__(self, app=None):
        """Initialize the DataWarehouseDB instance."""
        self.connector = None
        self.engine = None
        if app:
            self.init_app(app)

    def init_app(self, app, test_connection=True):
        """Initialize with option to skip connection test."""
        try:
            # Validate configuration
            required_configs = {
                "DW_UNIX_SOCKET": "Instance connection name",
                "DW_NAME": "Database name",
                "DW_IAM_USER": "IAM user email",
            }

            missing = [k for k in required_configs if not app.config.get(k)]
            if missing:
                raise ValueError(f"Missing configs: {', '.join(missing)}")

            self.connector = Connector()

            db_config = DBConfig(
                instance_connection_name=app.config["DW_UNIX_SOCKET"],
                database=app.config["DW_NAME"],
                user=app.config["DW_IAM_USER"],
                enable_iam_auth=True,
            )

            self.engine = create_engine(
                "postgresql+pg8000://",
                creator=lambda: self._get_iam_connection(db_config),
                pool_size=5,
                max_overflow=2,
                pool_timeout=10,
                pool_recycle=1800,
                connect_args={"use_native_uuid": False},
            )

            if test_connection:
                self._test_connection()

        except Exception as e:
            app.logger.error(f"Data Warehouse init failed: {str(e)}")
            if self.connector:
                self.connector.close()
            raise

    def _get_iam_connection(self, db_config: DBConfig):
        """Establish connection using IAM authentication."""
        return self.connector.connect(
            db_config.instance_connection_name,
            "pg8000",
            ip_type="public",
            db=db_config.database,
            user=db_config.user,
            enable_iam_auth=db_config.enable_iam_auth,
        )

    def _test_connection(self):
        """Test the database connection using proper SQLAlchemy text() construct."""
        with self.engine.connect() as conn:
            # Wrap the SQL string in text() for proper execution
            result = conn.execute(text("SELECT version()")).fetchone()
            print(f"Connection successful. Database version: {result[0]}")  # noqa: T201

    def teardown(self, exception=None):  # noqa: ARG002 - required by Flask interface
        """Clean up resources."""
        if self.connector:
            self.connector.close()

    @property
    def session(self):
        """Provide a database session."""
        return scoped_session(sessionmaker(bind=self.engine))


data_warehouse = DataWarehouseDB()
