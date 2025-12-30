"""Unit tests for authentication enforcement."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


@pytest.mark.parametrize(
    "is_logged_in,roles,should_deny",
    [
        (False, None, True),  # Not logged in
        (True, ["other-role"], True),  # Logged in but missing role
        (True, ["pay-report"], False),  # Has role
    ],
)
def test_enforce_auth(mock_streamlit, is_logged_in, roles, should_deny):
    """Test enforce_auth behavior for various authentication scenarios."""
    if roles is not None:
        mock_user = Mock()
        mock_user.is_logged_in = is_logged_in
        mock_user.get = Mock(return_value=roles)
        mock_streamlit.user = mock_user
    else:
        mock_streamlit.user.is_logged_in = is_logged_in

    modules_to_clear = ["src", "src.auth", "src.__init__"]
    for mod in modules_to_clear:
        sys.modules.pop(mod, None)

    with patch("src.auth.st", mock_streamlit):
        from src.auth import enforce_auth

        match (should_deny, is_logged_in):
            case (True, False):
                with pytest.raises(SystemExit):
                    enforce_auth()
                mock_streamlit.login.assert_called_once()
                mock_streamlit.stop.assert_called_once()
            case (True, True):
                with pytest.raises(SystemExit):
                    enforce_auth()
                mock_streamlit.error.assert_called_once()
                mock_streamlit.stop.assert_called_once()
            case (False, _):
                enforce_auth()
                mock_streamlit.stop.assert_not_called()
                mock_streamlit.login.assert_not_called()
                mock_streamlit.error.assert_not_called()


def test_module_level_enforce_auth_mocked(mock_enforce_auth):
    """Test that enforce_auth is mocked and doesn't stop execution."""
    modules_to_clear = ["src", "src.__init__"]
    for mod in modules_to_clear:
        if mod in sys.modules:
            sys.modules.pop(mod, None)

    import src  # noqa: F401

    assert mock_enforce_auth.called, (
        "enforce_auth should be called during src import"
    )


def test_get_db_connection_calls_enforce_auth(mock_streamlit):
    """Test that get_db_connection calls enforce_auth via require_keycloak_auth."""
    modules_to_clear = [
        "src.db_connection",
        "src.auth",
        "pg8000",
        "google.cloud.sql.connector",
    ]
    for mod in modules_to_clear:
        sys.modules.pop(mod, None)

    sys.modules["pg8000"] = Mock()
    sys.modules["google"] = Mock()
    sys.modules["google.cloud"] = Mock()
    sys.modules["google.cloud.sql"] = Mock()
    sys.modules["google.cloud.sql.connector"] = Mock()

    mock_streamlit.user.is_logged_in = False

    with patch("src.auth.st", mock_streamlit):
        from src.db_connection import get_db_connection

        with pytest.raises(SystemExit):
            get_db_connection()

        mock_streamlit.login.assert_called_once()
