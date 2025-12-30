import pg8000
import streamlit as st
from google.cloud.sql.connector import Connector, IPTypes

from .auth import require_keycloak_auth


# Keycloak Auth is enforced for the DB connection.
@require_keycloak_auth
def get_db_connection():
    """
    Get a database connection.

    Supports both regular PostgreSQL connections and Google Cloud SQL
    connections using cloud-sql-python-connector.

    For Cloud SQL, set instance_connection_name in database secrets.
    Uses pg8000 driver with IAM authentication (no password required).
    The connector uses Application Default Credentials (ADC) for authentication.

    For regular connections, use host/port in database secrets.
    """
    try:
        db_config = st.secrets.get("database", {})
        instance_connection_name = db_config.get("instance_connection")

        if instance_connection_name:
            # For PAY-DB string, not DW.
            if instance_connection_name.startswith("/cloudsql/"):
                instance_connection_name = instance_connection_name[10:]
            connector = Connector()
            # Use IAM authentication - no password needed
            # The connector uses Application Default Credentials (ADC)
            conn = connector.connect(
                instance_connection_name,
                "pg8000",
                user=db_config.get("username", "postgres"),
                db=db_config.get("database", "postgres"),
                ip_type=IPTypes.PUBLIC,
            )
            return conn

        # Regular PostgreSQL connection using pg8000
        conn = pg8000.connect(
            host=db_config.get("host", "localhost"),
            port=int(db_config.get("port", "5432")),
            database=db_config.get("name", "postgres"),
            user=db_config.get("username", "postgres"),
            password=db_config.get("password", ""),
        )
        return conn
    except Exception as e:
        raise Exception(f"Database connection error: {str(e)}")


# Keycloak Auth is enforced for the query execution.
@require_keycloak_auth
def execute_query(query, params=None):
    """
    Execute a query and return the results.

    Uses parameterized queries to prevent SQL injection.
    All user input must be passed via the params argument, never
    interpolated directly into the query string.

    Args:
        query: SQL query string with %s placeholders for parameters
        params: Tuple, list, or dict of parameters to substitute

    Returns:
        List of dictionaries representing query results

    Raises:
        Exception: If query execution fails
    """
    if not isinstance(query, str):
        raise TypeError("Query must be a string")

    # Ensure params is a tuple/list if provided (not None)
    # This prevents accidental string formatting
    if params is None:
        params = ()

    conn = get_db_connection()
    try:
        # pg8000 connection
        cursor = conn.cursor()
        cursor.execute(query, params)
        columns = (
            [desc[0] for desc in cursor.description]
            if cursor.description
            else []
        )
        rows = cursor.fetchall()
        results = [dict(zip(columns, row, strict=True)) for row in rows]
        cursor.close()
        return results
    except Exception as e:
        raise Exception(f"Query execution error: {str(e)}")
    finally:
        conn.close()
