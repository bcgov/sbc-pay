"""Unit tests for generate_toml_secrets function."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from scripts.generate_toml_secrets import generate_toml_secrets


def test_generate_toml_secrets():
    """Test generating secrets.toml with auth and database environment variables."""
    env_vars = {
        "STREAMLIT_AUTH_CLIENT_ID": "test-client-id",
        "STREAMLIT_AUTH_CLIENT_SECRET": "test-client-secret",
        "STREAMLIT_DATABASE_NAME": "test-db",
        "STREAMLIT_DATABASE_HOST": "localhost",
    }

    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "nested" / "dir" / "secrets.toml"

        with patch.dict(os.environ, env_vars, clear=False):
            generate_toml_secrets(output_path)

        assert output_path.exists()
        assert output_path.parent.exists()

        content = output_path.read_text()
        assert "[auth]" in content
        assert "[database]" in content
        assert 'client_id = "test-client-id"' in content
        assert 'name = "test-db"' in content


@pytest.mark.parametrize(
    "env_vars,should_create_file",
    [
        ({}, False),
        ({"OTHER_VAR": "should-be-ignored"}, False),
        ({"STREAMLIT_": "no-section"}, False),
        ({"STREAMLIT_NOSEPARATOR": "no-underscore"}, False),
        ({"STREAMLIT_AUTH": "no-key"}, False),
    ],
)
def test_generate_toml_secrets_edge_cases(env_vars, should_create_file):
    """Test edge cases: no vars, invalid vars."""
    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "secrets.toml"

        with patch.dict(os.environ, env_vars, clear=True):
            generate_toml_secrets(output_path)

        if should_create_file:
            assert output_path.exists()
        else:
            assert not output_path.exists()
