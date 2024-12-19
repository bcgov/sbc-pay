"""Test utils functions."""

import pytest

from utils.google_bucket import upload_to_bucket


@pytest.mark.skip(reason="Adhoc test.")
def test_bucket_upload(app):
    """Test upload to bucket."""
    upload_to_bucket("README.md", "README.md")
    assert True
