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

"""Tests to assure the accounts end-point.

Test-Suite to ensure that the /accounts endpoint is working as expected.
"""

import json
from datetime import datetime, timedelta, timezone

import dateutil

from pay_api.models.invoice import Invoice
from pay_api.models.payment_account import PaymentAccount
from pay_api.utils.enums import StatementFrequency
from pay_api.utils.util import (
    current_local_time,
    get_first_and_last_dates_of_month,
    get_week_start_and_end_date,
)
from tests.utilities.base_test import get_claims, get_payment_request, token_header
from pay_api.utils.constants import DT_SHORT_FORMAT


def test_get_default_statement_settings_weekly(session, client, jwt, app):
    """Assert that the default statement setting is weekly."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    rv = client.get(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/settings",
        headers=headers,
    )
    assert rv.status_code == 200
    assert (
        rv.json.get("currentFrequency").get("frequency")
        == StatementFrequency.WEEKLY.value
    )
    # Assert the array of the frequncies
    for freqeuncy in rv.json.get("frequencies"):
        if freqeuncy.get("frequency") == StatementFrequency.WEEKLY.value:
            actual_weekly = dateutil.parser.parse(freqeuncy.get("startDate")).date()
            expected_weekly = (
                get_week_start_and_end_date()[1] + timedelta(days=1)
            ).date()
            assert actual_weekly == expected_weekly, "weekly matches"
        if freqeuncy.get("frequency") == StatementFrequency.MONTHLY.value:
            today = datetime.now(tz=timezone.utc)
            actual_monthly = dateutil.parser.parse(freqeuncy.get("startDate")).date()
            expected_monthly = (
                get_first_and_last_dates_of_month(today.month, today.year)[1]
                + timedelta(days=1)
            ).date()
            assert actual_monthly == expected_monthly, "monthly matches"
        if freqeuncy.get("frequency") == StatementFrequency.DAILY.value:
            actual_daily = dateutil.parser.parse(freqeuncy.get("startDate")).date()
            # since current frequncy is weekly , daily changes will happen at the end of the week
            expected_weekly = (
                get_week_start_and_end_date()[1] + timedelta(days=1)
            ).date()
            assert actual_daily == expected_weekly, "daily matches"


def test_post_default_statement_settings_daily(session, client, jwt, app):
    """Assert that the post endpoint works."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.post(
        "/api/v1/payment-requests",
        data=json.dumps(get_payment_request(business_identifier="CP0002000")),
        headers=headers,
    )

    invoice: Invoice = Invoice.find_by_id(rv.json.get("id"))
    pay_account: PaymentAccount = PaymentAccount.find_by_id(invoice.payment_account_id)

    rv = client.get(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/settings",
        data=json.dumps({}),
        headers=headers,
    )
    assert rv.status_code == 200
    assert (
        rv.json.get("currentFrequency").get("frequency")
        == StatementFrequency.WEEKLY.value
    )

    # Set the frequency to Daily and assert
    daily_frequency = {"frequency": "DAILY"}
    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/settings",
        data=json.dumps(daily_frequency),
        headers=headers,
    )
    assert rv.json.get("frequency") == StatementFrequency.DAILY.value
    end_date = get_week_start_and_end_date()[1]
    assert rv.json.get("fromDate") == (end_date + timedelta(days=1)).strftime(
        DT_SHORT_FORMAT
    )

    # Set the frequency to Monthly and assert
    daily_frequency = {"frequency": "MONTHLY"}
    rv = client.post(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/settings",
        data=json.dumps(daily_frequency),
        headers=headers,
    )
    end_date = get_first_and_last_dates_of_month(
        current_local_time().month, current_local_time().year
    )[1]
    assert rv.json.get("frequency") == StatementFrequency.MONTHLY.value
    assert rv.json.get("fromDate") == (end_date + timedelta(days=1)).strftime(
        DT_SHORT_FORMAT
    )

    # Get the latest frequency
    rv = client.get(
        f"/api/v1/accounts/{pay_account.auth_account_id}/statements/settings",
        data=json.dumps({}),
        headers=headers,
    )
    assert rv.status_code == 200
    assert (
        rv.json.get("currentFrequency").get("frequency")
        == StatementFrequency.MONTHLY.value
    )
