"""Pytest configuration and fixtures."""

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture
def mock_streamlit():
    """Create a mock Streamlit module."""
    mock_st = MagicMock()
    mock_st.user = Mock()
    mock_st.user.is_logged_in = True
    mock_st.login = Mock()
    mock_st.stop = Mock(side_effect=SystemExit)
    mock_st.error = Mock()
    return mock_st


# Create mock streamlit module and inject it into sys.modules
# This must happen before any src modules are imported
_mock_streamlit = MagicMock()
_mock_user = Mock()
_mock_user.is_logged_in = True
_mock_user.get = Mock(
    return_value=["pay-report"]
)  # Default to having the role
_mock_streamlit.user = _mock_user
_mock_streamlit.login = Mock()
_mock_streamlit.stop = Mock(side_effect=SystemExit)
_mock_streamlit.error = Mock()

# Inject mock into sys.modules before src imports streamlit
if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = _mock_streamlit


@pytest.fixture(autouse=True)
def mock_enforce_auth():
    """Mock enforce_auth to prevent execution during module import."""
    # Patch enforce_auth to do nothing (no execution, no st.stop())
    # This prevents the module-level call from stopping test execution
    with patch("src.auth.enforce_auth", return_value=None) as mock:
        yield mock
