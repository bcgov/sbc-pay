# Copyright © 2026 Province of British Columbia
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

"""Tests to assure the user context account id resolution."""

import pytest
from flask import g

from pay_api.utils.user_context import get_auth_account_id


@pytest.mark.parametrize(
    "token_info, g_account_id, header, expected",
    [
        ({"Account-Id": "111"}, "222", "333", "111"),
        ({}, "222", "333", "222"),
        ({}, None, "333", None),
        ({}, "<unset>", "333", "333"),
        ({}, "<unset>", None, None),
    ],
)
def test_get_auth_account_id(app, token_info, g_account_id, header, expected):
    """Assert token claim wins, then the account resolved by check_auth, then the header."""
    headers = {"Account-Id": header} if header else {}
    with app.test_request_context(headers=headers):
        g.jwt_oidc_token_info = token_info
        if g_account_id != "<unset>":
            g.account_id = g_account_id
        assert get_auth_account_id() == expected
