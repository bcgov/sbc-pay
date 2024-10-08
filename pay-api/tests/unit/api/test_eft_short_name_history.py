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

"""Tests to assure the EFT short names history end-point.

Test-Suite to ensure that the /eft-shortnames/{id}/history endpoint is working as expected.
"""
from datetime import datetime

import pytest
from freezegun import freeze_time

from pay_api.services.eft_short_name_historical import (
    EFTShortnameHistorical as EFTHistoryService,
)
from pay_api.services.eft_short_name_historical import EFTShortnameHistory as EFTHistory
from pay_api.utils.enums import EFTHistoricalTypes, InvoiceStatus, PaymentMethod, Role
from tests.utilities.base_test import (
    factory_eft_refund,
    factory_eft_shortname,
    factory_invoice,
    factory_payment_account,
    get_claims,
    token_header,
)


def setup_test_data(exclude_history: bool = False):
    """Set up eft short name historical data."""
    payment_account = factory_payment_account(
        payment_method_code=PaymentMethod.EFT.value,
        auth_account_id="1234",
        name="ABC-BRANCH",
        branch_name="BRANCH",
    ).save()
    short_name = factory_eft_shortname(short_name="TESTSHORTNAME1").save()

    if not exclude_history:
        EFTHistoryService.create_funds_received(
            EFTHistory(short_name_id=short_name.id, amount=351.50, credit_balance=351.50)
        ).save()

        EFTHistoryService.create_statement_paid(
            EFTHistory(
                short_name_id=short_name.id,
                amount=351.50,
                credit_balance=0,
                payment_account_id=payment_account.id,
                related_group_link_id=1,
                statement_number=1234,
            )
        ).save()

        EFTHistoryService.create_statement_reverse(
            EFTHistory(
                short_name_id=short_name.id,
                amount=351.50,
                credit_balance=351.50,
                payment_account_id=payment_account.id,
                related_group_link_id=2,
                statement_number=1234,
            )
        ).save()

    return payment_account, short_name


@pytest.mark.parametrize(
    "result_index, expected_values",
    [
        (
            0,
            {
                "isReversible": False,
                "accountBranch": "BRANCH",
                "accountName": "ABC",
                "amount": 351.50,
                "shortNameBalance": 351.50,
                "statementNumber": 1234,
                "invoiceId": None,
                "transactionType": EFTHistoricalTypes.STATEMENT_REVERSE.value,
            },
        ),
        (
            1,
            {
                "isReversible": False,
                "accountBranch": "BRANCH",
                "accountName": "ABC",
                "amount": 351.50,
                "shortNameBalance": 0,
                "statementNumber": 1234,
                "invoiceId": None,
                "transactionType": EFTHistoricalTypes.STATEMENT_PAID.value,
            },
        ),
    ],
)
def test_search_statement_history(session, result_index, expected_values, client, jwt, app):
    """Assert that EFT short names statement history can be searched."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    transaction_date = datetime(2024, 7, 31, 0, 0, 0)
    with freeze_time(transaction_date):
        payment_account, short_name = setup_test_data()
        rv = client.get(f"/api/v1/eft-shortnames/{short_name.id}/history", headers=headers)
        assert rv.status_code == 200

        result_dict = rv.json
        assert result_dict is not None
        assert result_dict["page"] == 1
        assert result_dict["total"] == 3
        assert result_dict["limit"] == 10
        assert result_dict["items"] is not None
        assert len(result_dict["items"]) == 3

        transaction_date = EFTHistoryService.transaction_date_now().strftime("%Y-%m-%dT%H:%M:%S")
        statement_history = result_dict["items"][result_index]
        assert statement_history["historicalId"] is not None
        assert statement_history["isReversible"] == expected_values["isReversible"]
        assert statement_history["accountId"] == payment_account.auth_account_id
        assert statement_history["accountBranch"] == expected_values["accountBranch"]
        assert statement_history["accountName"] == expected_values["accountName"]
        assert statement_history["amount"] == expected_values["amount"]
        assert statement_history["shortNameBalance"] == expected_values["shortNameBalance"]
        assert statement_history["shortNameId"] == short_name.id
        assert statement_history["invoiceId"] == expected_values["invoiceId"]
        assert statement_history["statementNumber"] == expected_values["statementNumber"]
        assert statement_history["transactionType"] == expected_values["transactionType"]
        assert statement_history["transactionDate"] == transaction_date


def test_search_funds_received_history(session, client, jwt, app):
    """Assert that EFT short names funds received history can be searched."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    transaction_date = datetime(2024, 7, 31, 0, 0, 0)
    with freeze_time(transaction_date):
        payment_account, short_name = setup_test_data()
        rv = client.get(f"/api/v1/eft-shortnames/{short_name.id}/history", headers=headers)
        assert rv.status_code == 200

        result_dict = rv.json
        assert result_dict is not None
        assert result_dict["page"] == 1
        assert result_dict["total"] == 3
        assert result_dict["limit"] == 10
        assert result_dict["items"] is not None
        assert len(result_dict["items"]) == 3

        transaction_date = EFTHistoryService.transaction_date_now().strftime("%Y-%m-%dT%H:%M:%S")
        funds_received = result_dict["items"][2]
        assert funds_received["historicalId"] is not None
        assert funds_received["isReversible"] is False
        assert funds_received["accountBranch"] is None
        assert funds_received["accountId"] is None
        assert funds_received["accountName"] is None
        assert funds_received["amount"] == 351.50
        assert funds_received["shortNameBalance"] == 351.50
        assert funds_received["shortNameId"] == short_name.id
        assert funds_received["statementNumber"] is None
        assert funds_received["invoiceId"] is None
        assert funds_received["transactionType"] == EFTHistoricalTypes.FUNDS_RECEIVED.value
        assert funds_received["transactionDate"] == transaction_date


def test_search_invoice_refund_history(session, client, jwt, app):
    """Assert that EFT short names invoice refund history can be searched."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    transaction_date = datetime(2024, 7, 31, 0, 0, 0)
    with freeze_time(transaction_date):
        payment_account, short_name = setup_test_data(exclude_history=True)
        invoice = factory_invoice(
            payment_account,
            payment_method_code=PaymentMethod.EFT.value,
            status_code=InvoiceStatus.REFUND_REQUESTED.value,
            total=50,
            paid=50,
        ).save()

        EFTHistoryService.create_invoice_refund(
            EFTHistory(
                short_name_id=short_name.id,
                amount=50,
                credit_balance=50,
                payment_account_id=payment_account.id,
                related_group_link_id=1,
                statement_number=1234,
                invoice_id=invoice.id,
            )
        ).save()

        rv = client.get(f"/api/v1/eft-shortnames/{short_name.id}/history", headers=headers)
        result_dict = rv.json
        assert result_dict is not None
        assert result_dict["page"] == 1
        assert result_dict["total"] == 1
        assert result_dict["limit"] == 10
        assert result_dict["items"] is not None
        assert len(result_dict["items"]) == 1

        transaction_date = EFTHistoryService.transaction_date_now().strftime("%Y-%m-%dT%H:%M:%S")
        invoice_refund = result_dict["items"][0]
        assert invoice_refund["historicalId"] is not None
        assert invoice_refund["isReversible"] is False
        assert invoice_refund["accountId"] == payment_account.auth_account_id
        assert invoice_refund["accountBranch"] == payment_account.branch_name
        assert invoice_refund["accountName"] == "ABC"
        assert invoice_refund["amount"] == 50
        assert invoice_refund["shortNameBalance"] == 50
        assert invoice_refund["shortNameId"] == short_name.id
        assert invoice_refund["invoiceId"] == invoice.id
        assert invoice_refund["statementNumber"] == 1234
        assert invoice_refund["transactionType"] == EFTHistoricalTypes.INVOICE_REFUND.value
        assert invoice_refund["transactionDate"] == transaction_date


def test_search_shortname_refund_history(session, client, jwt, app):
    """Assert that EFT short names refund history can be searched."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    transaction_date = datetime(2024, 7, 31, 0, 0, 0)
    with freeze_time(transaction_date):
        payment_account, short_name = setup_test_data(exclude_history=True)
        eft_refund = factory_eft_refund(short_name.id, refund_amount=100).save()
        EFTHistoryService.create_shortname_refund(
            EFTHistory(
                short_name_id=short_name.id,
                amount=100,
                credit_balance=0,
                eft_refund_id=eft_refund.id,
                is_processing=False,
                hidden=False,
            )
        ).save()

        rv = client.get(f"/api/v1/eft-shortnames/{short_name.id}/history", headers=headers)
        result_dict = rv.json
        assert result_dict is not None
        assert result_dict["page"] == 1
        assert result_dict["total"] == 1
        assert result_dict["limit"] == 10
        assert result_dict["items"] is not None
        assert len(result_dict["items"]) == 1

        transaction_date = EFTHistoryService.transaction_date_now().strftime("%Y-%m-%dT%H:%M:%S")
        invoice_refund = result_dict["items"][0]
        assert invoice_refund["historicalId"] is not None
        assert invoice_refund["isReversible"] is False
        assert invoice_refund["accountId"] is None
        assert invoice_refund["accountBranch"] is None
        assert invoice_refund["accountName"] is None
        assert invoice_refund["amount"] == 100
        assert invoice_refund["shortNameBalance"] == 0
        assert invoice_refund["shortNameId"] == short_name.id
        assert invoice_refund["invoiceId"] is None
        assert invoice_refund["statementNumber"] is None
        assert invoice_refund["transactionType"] == EFTHistoricalTypes.SN_REFUND_PENDING_APPROVAL.value
        assert invoice_refund["transactionDate"] == transaction_date


def test_search_statement_paid_is_reversible(session, client, jwt, app):
    """Assert that EFT short names statement paid is reversible."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    transaction_date = datetime(2024, 7, 31, 0, 0, 0)
    with freeze_time(transaction_date):
        payment_account, short_name = setup_test_data(exclude_history=True)
        EFTHistoryService.create_statement_paid(
            EFTHistory(
                short_name_id=short_name.id,
                amount=351.50,
                credit_balance=0,
                payment_account_id=payment_account.id,
                related_group_link_id=1,
                statement_number=1234,
            )
        ).save()

        rv = client.get(f"/api/v1/eft-shortnames/{short_name.id}/history", headers=headers)
        assert rv.status_code == 200
        result_dict = rv.json
        history = result_dict["items"][0]
        assert history["isReversible"] is True
        assert history["transactionType"] == EFTHistoricalTypes.STATEMENT_PAID.value
