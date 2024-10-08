# Copyright © 2024 Province of British Columbia
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

"""Tests for Email Service."""

import json
from unittest.mock import patch

from pay_api.services.email_service import send_email
from pay_api.utils.enums import AuthHeaderType, ContentType


def test_send_email(app, monkeypatch):
    """Test send email."""
    app.config["NOTIFY_API_ENDPOINT"] = "http://test_notify_api_endpoint/"

    monkeypatch.setattr("pay_api.services.email_service.get_service_account_token", lambda: "test")

    with app.app_context():
        with patch("pay_api.services.email_service.OAuthService.post") as mock_post:
            mock_post.return_value.text = json.dumps({"notifyStatus": "SUCCESS"})
            result = send_email(["recipient@example.com"], "Subject", "Body")
            mock_post.assert_called_with(
                "http://test_notify_api_endpoint/notify/",
                token="test",
                auth_header_type=AuthHeaderType.BEARER,
                content_type=ContentType.JSON,
                data={
                    "recipients": "recipient@example.com",
                    "content": {"subject": "Subject", "body": "Body"},
                },
            )
        assert result is True
