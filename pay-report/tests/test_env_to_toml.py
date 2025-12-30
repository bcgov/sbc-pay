"""Unit tests for env_to_toml conversion script."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from env_to_toml import convert_env_to_toml  # noqa: E402


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def vaults_gcp_env_file():
    """Return path to actual vaults.gcp.env file."""
    return os.path.join(
        os.path.dirname(__file__), "..", "devops", "vaults.gcp.env"
    )


@pytest.mark.parametrize(
    "expected_key,expected_value",
    [
        (
            "redirect_uri",
            "op://keycloak/$APP_ENV/pay-report/AUTH_REDIRECT_URI",
        ),
        (
            "cookie_secret",
            "op://keycloak/$APP_ENV/pay-report/AUTH_COOKIE_SECRET",
        ),
        (
            "client_id",
            "op://keycloak/$APP_ENV/pay-report/AUTH_CLIENT_ID",
        ),
        (
            "client_secret",
            "op://keycloak/$APP_ENV/pay-report/AUTH_CLIENT_SECRET",
        ),
        (
            "server_metadata_url",
            "op://keycloak/$APP_ENV/jwt-base/JWT_OIDC_WELL_KNOWN_CONFIG",
        ),
    ],
)
def test_convert_auth_variables(
    vaults_gcp_env_file, temp_dir, expected_key, expected_value
):
    """Test conversion of AUTH_ prefixed variables from vaults.gcp.env."""
    output_file = os.path.join(temp_dir, "secrets.toml")

    convert_env_to_toml(vaults_gcp_env_file, output_file)

    assert os.path.exists(output_file)
    content = Path(output_file).read_text()
    assert "[auth]" in content
    assert f'{expected_key} = "{expected_value}"' in content


@pytest.mark.parametrize(
    "expected_key,expected_value",
    [
        (
            "name",
            "op://database/$APP_ENV/pay-db-gcp/DATABASE_NAME",
        ),
        (
            "password",
            "op://database/$APP_ENV/pay-db-gcp/DATABASE_PASSWORD",
        ),
        (
            "port",
            "op://database/$APP_ENV/pay-db-gcp/DATABASE_PORT",
        ),
        (
            "instance_connection",
            "op://database/$APP_ENV/pay-db-gcp/DATABASE_UNIX_SOCKET",
        ),
        (
            "username",
            "op://database/$APP_ENV/pay-db-gcp/DATABASE_USERNAME",
        ),
    ],
)
def test_convert_database_variables(
    vaults_gcp_env_file, temp_dir, expected_key, expected_value
):
    """Test DATABASE_ variables from vaults.gcp.env."""
    output_file = os.path.join(temp_dir, "secrets.toml")

    convert_env_to_toml(vaults_gcp_env_file, output_file)

    assert os.path.exists(output_file)
    content = Path(output_file).read_text()
    assert "[database]" in content
    assert f'{expected_key} = "{expected_value}"' in content


def test_convert_both_sections(vaults_gcp_env_file, temp_dir):
    """Test both AUTH_ and DATABASE_ variables from vaults.gcp.env."""
    output_file = os.path.join(temp_dir, "secrets.toml")

    convert_env_to_toml(vaults_gcp_env_file, output_file)

    assert os.path.exists(output_file)
    content = Path(output_file).read_text()
    assert "[auth]" in content
    assert "[database]" in content
    assert (
        'client_id = "op://keycloak/$APP_ENV/pay-report/AUTH_CLIENT_ID"'
        in content
    )
    assert (
        'name = "op://database/$APP_ENV/pay-db-gcp/DATABASE_NAME"' in content
    )


@pytest.mark.parametrize(
    "input_value,expected_output",
    [
        ('"quoted-value"', "quoted-value"),
        ("'single-quoted'", "single-quoted"),
    ],
)
def test_remove_quotes(temp_dir, input_value, expected_output):
    """Test that quotes are removed from values."""
    env_file = os.path.join(temp_dir, ".env")
    output_file = os.path.join(temp_dir, "secrets.toml")

    with open(env_file, "w", encoding="utf-8") as f:
        f.write(f"AUTH_CLIENT_ID={input_value}\n")

    convert_env_to_toml(env_file, output_file)

    content = Path(output_file).read_text()
    assert f'client_id = "{expected_output}"' in content


def test_skip_comments(temp_dir):
    """Test that comment lines are skipped."""
    env_file = os.path.join(temp_dir, ".env")
    output_file = os.path.join(temp_dir, "secrets.toml")

    with open(env_file, "w", encoding="utf-8") as f:
        f.write("# This is a comment\n")
        f.write("AUTH_CLIENT_ID=value\n")
        f.write("# Another comment\n")

    convert_env_to_toml(env_file, output_file)

    content = Path(output_file).read_text()
    assert "# This is a comment" not in content
    assert "# Another comment" not in content
    assert 'client_id = "value"' in content


def test_skip_empty_lines(temp_dir):
    """Test that empty lines are skipped."""
    env_file = os.path.join(temp_dir, ".env")
    output_file = os.path.join(temp_dir, "secrets.toml")

    with open(env_file, "w", encoding="utf-8") as f:
        f.write("\n")
        f.write("AUTH_CLIENT_ID=value\n")
        f.write("\n")
        f.write("DATABASE_HOST=localhost\n")
        f.write("\n")

    convert_env_to_toml(env_file, output_file)

    content = Path(output_file).read_text()
    lines = [line for line in content.split("\n") if line.strip()]
    assert len(lines) > 0
    assert 'client_id = "value"' in content
    assert 'host = "localhost"' in content


def test_skip_lines_without_equals(temp_dir):
    """Test that lines without = are skipped."""
    env_file = os.path.join(temp_dir, ".env")
    output_file = os.path.join(temp_dir, "secrets.toml")

    with open(env_file, "w", encoding="utf-8") as f:
        f.write("AUTH_CLIENT_ID=value\n")
        f.write("INVALID_LINE_NO_EQUALS\n")
        f.write("DATABASE_HOST=localhost\n")

    convert_env_to_toml(env_file, output_file)

    content = Path(output_file).read_text()
    assert "INVALID_LINE_NO_EQUALS" not in content
    assert 'client_id = "value"' in content
    assert 'host = "localhost"' in content


def test_ignore_non_prefixed_variables(temp_dir):
    """Test that variables without AUTH_ or DATABASE_ prefix are ignored."""
    env_file = os.path.join(temp_dir, ".env")
    output_file = os.path.join(temp_dir, "secrets.toml")

    with open(env_file, "w", encoding="utf-8") as f:
        f.write("AUTH_CLIENT_ID=value\n")
        f.write("OTHER_VAR=ignored\n")
        f.write("DATABASE_HOST=localhost\n")

    convert_env_to_toml(env_file, output_file)

    content = Path(output_file).read_text()
    assert "OTHER_VAR" not in content
    assert "ignored" not in content
    assert 'client_id = "value"' in content
    assert 'host = "localhost"' in content


def test_nonexistent_input_file(temp_dir, capsys):
    """Test handling of non-existent input file."""
    output_file = os.path.join(temp_dir, "secrets.toml")
    nonexistent_file = os.path.join(temp_dir, "nonexistent.env")

    convert_env_to_toml(nonexistent_file, output_file)

    assert not os.path.exists(output_file)
    captured = capsys.readouterr()
    assert "Warning" in captured.out
    assert "nonexistent.env" in captured.out


def test_create_output_directory(temp_dir):
    """Test that output directory is created if it doesn't exist."""
    env_file = os.path.join(temp_dir, ".env")
    output_dir = os.path.join(temp_dir, "nested", "dir")
    output_file = os.path.join(output_dir, "secrets.toml")

    with open(env_file, "w", encoding="utf-8") as f:
        f.write("AUTH_CLIENT_ID=value\n")

    convert_env_to_toml(env_file, output_file)

    assert os.path.exists(output_file)
    assert os.path.isdir(output_dir)


def test_empty_sections_not_written(temp_dir):
    """Test that empty sections are not written to output."""
    env_file = os.path.join(temp_dir, ".env")
    output_file = os.path.join(temp_dir, "secrets.toml")

    with open(env_file, "w", encoding="utf-8") as f:
        f.write("AUTH_CLIENT_ID=value\n")

    convert_env_to_toml(env_file, output_file)

    content = Path(output_file).read_text()
    assert "[auth]" in content
    assert "[database]" not in content


@pytest.mark.parametrize(
    "env_key,expected_toml_key",
    [
        ("AUTH_CLIENT_ID", "client_id"),
        ("AUTH_SERVER_METADATA_URL", "server_metadata_url"),
        ("DATABASE_INSTANCE_CONNECTION", "instance_connection"),
    ],
)
def test_key_transformation(temp_dir, env_key, expected_toml_key):
    """Test key transformation (AUTH_CLIENT_ID -> client_id)."""
    env_file = os.path.join(temp_dir, ".env")
    output_file = os.path.join(temp_dir, "secrets.toml")

    with open(env_file, "w", encoding="utf-8") as f:
        f.write(f"{env_key}=value\n")

    convert_env_to_toml(env_file, output_file)

    content = Path(output_file).read_text()
    assert expected_toml_key in content
    assert env_key not in content


def test_values_with_spaces(temp_dir):
    """Test handling of values with spaces."""
    env_file = os.path.join(temp_dir, ".env")
    output_file = os.path.join(temp_dir, "secrets.toml")

    with open(env_file, "w", encoding="utf-8") as f:
        f.write('AUTH_CLIENT_ID="value with spaces"\n')
        f.write("DATABASE_HOST=host with spaces\n")

    convert_env_to_toml(env_file, output_file)

    content = Path(output_file).read_text()
    assert 'client_id = "value with spaces"' in content
    assert 'host = "host with spaces"' in content


def test_multiple_equals_in_value(temp_dir):
    """Test handling of values containing = character."""
    env_file = os.path.join(temp_dir, ".env")
    output_file = os.path.join(temp_dir, "secrets.toml")

    with open(env_file, "w", encoding="utf-8") as f:
        f.write("AUTH_SERVER_METADATA_URL=http://example.com/path?key=value\n")

    convert_env_to_toml(env_file, output_file)

    content = Path(output_file).read_text()
    assert (
        'server_metadata_url = "http://example.com/path?key=value"' in content
    )
