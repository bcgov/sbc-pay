# Copyright © 2023 Province of British Columbia
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
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from pay_api.dtos.eft_shortname import EFTShortNameRefundPatchRequest, EFTShortNameRefundPostRequest
from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTCreditInvoiceLink as EFTCreditInvoiceModel
from pay_api.models import EFTFile as EFTFileModel
from pay_api.models import EFTShortnameLinks as EFTShortnameLinksModel
from pay_api.models import EFTShortnames as EFTShortnamesModel
from pay_api.models import EFTShortnamesHistorical as EFTShortnamesHistoryModel
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models.eft_refund import EFTRefund as EFTRefundModel
from pay_api.utils.enums import (
    APRefundMethod,
    ChequeRefundStatus,
    EFTCreditInvoiceStatus,
    EFTFileLineType,
    EFTHistoricalTypes,
    EFTPaymentActions,
    EFTProcessStatus,
    EFTShortnameRefundStatus,
    EFTShortnameStatus,
    EFTShortnameType,
    InvoiceStatus,
    PaymentMethod,
    Role,
    StatementFrequency,
)
from pay_api.utils.errors import Error
from pay_api.utils.util import iso_string_to_date
from tests.utilities.base_test import (
    factory_eft_credit,
    factory_eft_file,
    factory_eft_history,
    factory_eft_refund,
    factory_eft_shortname,
    factory_eft_shortname_link,
    factory_invoice,
    factory_payment_account,
    factory_statement,
    factory_statement_invoices,
    factory_statement_settings,
    get_claims,
    token_header,
)


def test_create_eft_short_name_link(session, client, jwt, app):
    """Assert that an EFT short name link can be created for an account with no credits or statements owing."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value], username="IDIR/JSMITH"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    factory_payment_account(payment_method_code=PaymentMethod.EFT.value, auth_account_id="1234").save()

    short_name = factory_eft_shortname(short_name="TESTSHORTNAME").save()
    rv = client.post(
        f"/api/v1/eft-shortnames/{short_name.id}/links",
        data=json.dumps({"accountId": "1234"}),
        headers=headers,
    )
    link_dict = rv.json
    assert rv.status_code == 200
    assert link_dict is not None
    assert link_dict["id"] is not None
    assert link_dict["shortNameId"] == short_name.id
    assert link_dict["statusCode"] == EFTShortnameStatus.PENDING.value
    assert link_dict["accountId"] == "1234"
    assert link_dict["updatedBy"] == "IDIR/JSMITH"

    date_format = "%Y-%m-%dT%H:%M:%S.%f"
    assert datetime.strptime(link_dict["updatedOn"], date_format).date() == datetime.now(tz=timezone.utc).date()


def test_create_eft_short_name_link_with_credit_and_owing(db, session, client, jwt, app):
    """Assert that an EFT short name link can be created for an account with credit."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value], username="IDIR/JSMITH"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    payment_account = factory_payment_account(
        payment_method_code=PaymentMethod.EFT.value, auth_account_id="1234"
    ).save()

    short_name = factory_eft_shortname(short_name="TESTSHORTNAME").save()

    eft_file = factory_eft_file("test.txt")

    eft_credit_1 = EFTCreditModel()
    eft_credit_1.eft_file_id = eft_file.id
    eft_credit_1.amount = 100
    eft_credit_1.remaining_amount = 100
    eft_credit_1.short_name_id = short_name.id
    eft_credit_1.save()

    rv = client.post(
        f"/api/v1/eft-shortnames/{short_name.id}/links",
        data=json.dumps({"accountId": "1234"}),
        headers=headers,
    )
    link_dict = rv.json
    assert rv.status_code == 200
    assert link_dict is not None
    assert link_dict["id"] is not None
    assert link_dict["shortNameId"] == short_name.id
    assert link_dict["statusCode"] == EFTShortnameStatus.PENDING.value
    assert link_dict["accountId"] == "1234"
    assert link_dict["updatedBy"] == "IDIR/JSMITH"

    short_name_link_id = link_dict["id"]
    rv = client.patch(
        f"/api/v1/eft-shortnames/{short_name.id}/links/{short_name_link_id}",
        data=json.dumps({"statusCode": EFTShortnameStatus.INACTIVE.value}),
        headers=headers,
    )
    assert rv.status_code == 200

    invoice = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=50,
        paid=0,
    ).save()

    statement_settings = factory_statement_settings(
        payment_account_id=payment_account.id,
        frequency=StatementFrequency.MONTHLY.value,
    )
    statement = factory_statement(
        payment_account_id=payment_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=statement_settings.id,
    )
    factory_statement_invoices(statement_id=statement.id, invoice_id=invoice.id)

    rv = client.post(
        f"/api/v1/eft-shortnames/{short_name.id}/links",
        data=json.dumps({"accountId": "1234"}),
        headers=headers,
    )
    link_dict = rv.json
    assert rv.status_code == 200
    assert link_dict is not None
    assert link_dict["id"] is not None
    assert link_dict["shortNameId"] == short_name.id
    assert link_dict["statusCode"] == EFTShortnameStatus.PENDING.value
    assert link_dict["accountId"] == "1234"
    assert link_dict["updatedBy"] == "IDIR/JSMITH"

    assert eft_credit_1.amount == 100
    assert eft_credit_1.remaining_amount == 50
    assert eft_credit_1.short_name_id == short_name.id

    credit_invoice: EFTCreditInvoiceModel = (
        db.session.query(EFTCreditInvoiceModel)
        .filter(EFTCreditInvoiceModel.eft_credit_id == eft_credit_1.id)
        .filter(EFTCreditInvoiceModel.invoice_id == invoice.id)
    ).one_or_none()

    assert credit_invoice
    assert credit_invoice.eft_credit_id == eft_credit_1.id
    assert credit_invoice.invoice_id == invoice.id
    assert credit_invoice.status_code == EFTCreditInvoiceStatus.PENDING.value


def test_create_eft_short_name_link_validation(session, client, jwt, app):
    """Assert that invalid request is returned for existing short name link."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value], username="IDIR/JSMITH"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    short_name = factory_eft_shortname(short_name="TESTSHORTNAME").save()
    factory_eft_shortname_link(short_name_id=short_name.id, auth_account_id="1234", updated_by="IDIR/JSMITH").save()

    # Assert requires an auth account id for mapping
    rv = client.post(
        f"/api/v1/eft-shortnames/{short_name.id}/links",
        data=json.dumps({}),
        headers=headers,
    )

    link_dict = rv.json
    assert rv.status_code == 400
    assert link_dict["type"] == "EFT_SHORT_NAME_ACCOUNT_ID_REQUIRED"

    # Assert cannot create link to an existing mapped account id
    rv = client.post(
        f"/api/v1/eft-shortnames/{short_name.id}/links",
        data=json.dumps({"accountId": "1234"}),
        headers=headers,
    )

    link_dict = rv.json
    assert rv.status_code == 400
    assert link_dict["type"] == "EFT_SHORT_NAME_ALREADY_MAPPED"


def test_eft_short_name_unlink(session, client, jwt, app):
    """Assert that an EFT short name unlinking and basic state validation."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value], username="IDIR/JSMITH"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value, auth_account_id="1234").save()

    short_name = factory_eft_shortname(short_name="TESTSHORTNAME").save()
    short_name_link = EFTShortnameLinksModel(
        eft_short_name_id=short_name.id,
        status_code=EFTShortnameStatus.LINKED.value,
        auth_account_id=account.auth_account_id,
    ).save()

    rv = client.get(f"/api/v1/eft-shortnames/{short_name.id}/links", headers=headers)
    links = rv.json
    assert rv.status_code == 200
    assert links["items"]
    assert len(links["items"]) == 1

    # Assert valid link status state
    rv = client.patch(
        f"/api/v1/eft-shortnames/{short_name.id}/links/{short_name_link.id}",
        data=json.dumps({"statusCode": EFTShortnameStatus.LINKED.value}),
        headers=headers,
    )

    link_dict = rv.json
    assert rv.status_code == 400
    assert link_dict["type"] == Error.EFT_SHORT_NAME_LINK_INVALID_STATUS.name

    rv = client.patch(
        f"/api/v1/eft-shortnames/{short_name.id}/links/{short_name_link.id}",
        data=json.dumps({"statusCode": EFTShortnameStatus.INACTIVE.value}),
        headers=headers,
    )

    link_dict = rv.json
    assert rv.status_code == 200
    assert link_dict["statusCode"] == EFTShortnameStatus.INACTIVE.value

    rv = client.get(f"/api/v1/eft-shortnames/{short_name.id}/links", headers=headers)
    links = rv.json
    assert rv.status_code == 200
    assert not links["items"]


def test_get_eft_short_name_links(session, client, jwt, app):
    """Assert that short name links can be retrieved."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value], username="IDIR/JSMITH"), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    account = factory_payment_account(
        payment_method_code=PaymentMethod.EFT.value,
        auth_account_id="1234",
        name="ABC-123",
        branch_name="123",
    ).save()
    short_name = factory_eft_shortname(short_name="TESTSHORTNAME").save()

    invoice = factory_invoice(
        payment_account=account,
        payment_method_code=PaymentMethod.EFT.value,
        total=50,
        paid=0,
        status_code=InvoiceStatus.APPROVED.value,
    ).save()
    statement_settings = factory_statement_settings(
        payment_account_id=account.id, frequency=StatementFrequency.MONTHLY.value
    )
    statement = factory_statement(
        payment_account_id=account.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=statement_settings.id,
    )
    factory_statement_invoices(statement_id=statement.id, invoice_id=invoice.id)

    # Assert an empty result set is properly returned
    rv = client.get(f"/api/v1/eft-shortnames/{short_name.id}/links", headers=headers)

    link_dict = rv.json
    assert rv.status_code == 200
    assert link_dict is not None
    assert link_dict["items"] is not None
    assert len(link_dict["items"]) == 0

    # Create a short name link
    rv = client.post(
        f"/api/v1/eft-shortnames/{short_name.id}/links",
        data=json.dumps({"accountId": account.auth_account_id}),
        headers=headers,
    )

    link_dict = rv.json
    assert rv.status_code == 200

    # Assert link is returned in the result
    rv = client.get(f"/api/v1/eft-shortnames/{short_name.id}/links", headers=headers)

    link_list_dict = rv.json
    assert rv.status_code == 200
    assert link_list_dict is not None
    assert link_list_dict["items"] is not None
    assert len(link_list_dict["items"]) == 1

    link = link_list_dict["items"][0]
    statements_owing = link["statementsOwing"]
    assert link["accountId"] == account.auth_account_id
    assert link["id"] == link_dict["id"]
    assert link["shortNameId"] == short_name.id
    assert link["accountId"] == account.auth_account_id
    assert link["accountName"] == "ABC"
    assert link["accountBranch"] == "123"
    assert link["amountOwing"] == invoice.total
    assert link["statementId"] == statement.id
    assert link["statusCode"] == EFTShortnameStatus.PENDING.value
    assert link["updatedBy"] == "IDIR/JSMITH"
    assert statements_owing
    assert statements_owing[0]["amountOwing"] == invoice.total
    assert statements_owing[0]["pendingPaymentsAmount"] == 0
    assert statements_owing[0]["pendingPaymentsCount"] == 0
    assert statements_owing[0]["statementId"] == statement.id

    invoice2 = factory_invoice(
        payment_account=account,
        payment_method_code=PaymentMethod.EFT.value,
        total=100,
        paid=0,
        status_code=InvoiceStatus.APPROVED.value,
    ).save()
    statement2 = factory_statement(
        payment_account_id=account.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=statement_settings.id,
    )
    factory_statement_invoices(statement_id=statement2.id, invoice_id=invoice2.id)
    eft_file = factory_eft_file()
    factory_eft_credit(
        eft_file_id=eft_file.id, short_name_id=short_name.id, amount=invoice.total, remaining_amount=invoice.total
    )

    rv = client.post(
        f"/api/v1/eft-shortnames/{short_name.id}/payment",
        data=json.dumps(
            {
                "action": EFTPaymentActions.APPLY_CREDITS.value,
                "accountId": account.auth_account_id,
                "statementId": statement.id,
            }
        ),
        headers=headers,
    )

    rv = client.get(f"/api/v1/eft-shortnames/{short_name.id}/links", headers=headers)

    link_list_dict = rv.json
    assert rv.status_code == 200
    assert link_list_dict is not None
    assert link_list_dict["items"] is not None
    assert len(link_list_dict["items"]) == 1

    link = link_list_dict["items"][0]
    statements_owing = link["statementsOwing"]
    assert link["accountId"] == account.auth_account_id
    assert link["id"] == link_dict["id"]
    assert link["shortNameId"] == short_name.id
    assert link["accountId"] == account.auth_account_id
    assert link["accountName"] == "ABC"
    assert link["accountBranch"] == "123"
    assert link["amountOwing"] == invoice.total + invoice2.total
    assert link["statementId"] == statement2.id
    assert link["statusCode"] == EFTShortnameStatus.PENDING.value
    assert link["updatedBy"] == "IDIR/JSMITH"
    assert statements_owing
    assert len(statements_owing) == 2
    assert statements_owing[0]["amountOwing"] == invoice.total
    assert statements_owing[0]["pendingPaymentsAmount"] == invoice.total
    assert statements_owing[0]["pendingPaymentsCount"] == 1
    assert statements_owing[0]["statementId"] == statement.id
    assert statements_owing[1]["amountOwing"] == invoice2.total
    assert statements_owing[1]["pendingPaymentsAmount"] == 0
    assert statements_owing[1]["pendingPaymentsCount"] == 0
    assert statements_owing[1]["statementId"] == statement2.id


def assert_short_name_summary(
    result_dict: dict,
    short_name: EFTShortnamesModel,
    transaction: EFTTransactionModel,
    expected_credits_remaining: Decimal,
    expected_linked_accounts_count: int,
    shortname_refund: EFTRefundModel = None,
):
    """Assert short name summary result."""
    assert result_dict["id"] == short_name.id
    assert result_dict["shortName"] == short_name.short_name
    assert result_dict["shortNameType"] == short_name.type
    assert result_dict["creditsRemaining"] == expected_credits_remaining
    assert result_dict["linkedAccountsCount"] == expected_linked_accounts_count
    assert iso_string_to_date(result_dict["lastPaymentReceivedDate"]) == transaction.deposit_date
    assert result_dict["refundStatus"] == (shortname_refund.status if shortname_refund is not None else None)


def test_eft_short_name_summaries(session, client, jwt, app):
    """Assert that EFT short names summaries can be searched."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Assert initial search returns empty items
    rv = client.get("/api/v1/eft-shortnames/summaries", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 0

    # create test data
    factory_payment_account(
        payment_method_code=PaymentMethod.EFT.value,
        auth_account_id="1234",
        name="ABC-123",
        branch_name="123",
    ).save()

    short_name_1, s1_transaction1, short_name_2, s2_transaction1, s1_refund = create_eft_summary_search_data()

    # Assert short name search brings back both short names
    rv = client.get("/api/v1/eft-shortnames/summaries?shortName=SHORT", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 2
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 2
    assert_short_name_summary(result_dict["items"][0], short_name_1, s1_transaction1, 204.0, 0, s1_refund)
    assert_short_name_summary(
        result_dict["items"][1],
        short_name_2,
        s2_transaction1,
        302.5,
        1,
    )

    # Assert short name search brings back first short name
    rv = client.get("/api/v1/eft-shortnames/summaries?shortName=name1", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name_summary(result_dict["items"][0], short_name_1, s1_transaction1, 204.0, 0, s1_refund)

    # Assert search linked accounts count
    rv = client.get("/api/v1/eft-shortnames/summaries?linkedAccountsCount=0", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name_summary(result_dict["items"][0], short_name_1, s1_transaction1, 204.0, 0, s1_refund)

    rv = client.get("/api/v1/eft-shortnames/summaries?linkedAccountsCount=1", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name_summary(result_dict["items"][0], short_name_2, s2_transaction1, 302.5, 1)

    # Assert search by payment received date
    rv = client.get(
        "/api/v1/eft-shortnames/summaries?"
        "paymentReceivedStartDate=2024-01-16T08:00:00.000Z&paymentReceivedEndDate=2024-01-17T07:59:59.999Z",
        headers=headers,
    )
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name_summary(result_dict["items"][0], short_name_2, s2_transaction1, 302.5, 1)

    # Assert search by short name id
    rv = client.get(
        f"/api/v1/eft-shortnames/summaries?shortNameId={short_name_2.id}",
        headers=headers,
    )
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name_summary(result_dict["items"][0], short_name_2, s2_transaction1, 302.5, 1)

    # Assert search by remaining credits
    rv = client.get("/api/v1/eft-shortnames/summaries?creditsRemaining=204", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name_summary(result_dict["items"][0], short_name_1, s1_transaction1, 204.0, 0, s1_refund)

    # Assert search query by no state will return all records
    rv = client.get("/api/v1/eft-shortnames/summaries", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 2
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 2
    assert_short_name_summary(result_dict["items"][0], short_name_1, s1_transaction1, 204.0, 0, s1_refund)
    assert_short_name_summary(result_dict["items"][1], short_name_2, s2_transaction1, 302.5, 1)

    # Assert search pagination - page 1 works
    rv = client.get("/api/v1/eft-shortnames/summaries?page=1&limit=1", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 2
    assert result_dict["limit"] == 1
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name_summary(result_dict["items"][0], short_name_1, s1_transaction1, 204.0, 0, s1_refund)

    # Assert search pagination - page 2 works
    rv = client.get("/api/v1/eft-shortnames/summaries?page=2&limit=1", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 2
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 2
    assert result_dict["limit"] == 1
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name_summary(result_dict["items"][0], short_name_2, s2_transaction1, 302.5, 1)


def create_eft_summary_search_data():
    """Create seed data for EFT summary searches."""
    eft_file: EFTFileModel = factory_eft_file()
    short_name_1 = factory_eft_shortname(short_name="TESTSHORTNAME1").save()
    short_name_2 = factory_eft_shortname(
        short_name="TESTSHORTNAME2", short_name_type=EFTShortnameType.WIRE.value
    ).save()
    factory_eft_shortname_link(short_name_id=short_name_2.id, auth_account_id="1234", updated_by="IDIR/JSMITH").save()

    # short_name_1 transactions to test getting first payment
    s1_transaction1: EFTTransactionModel = EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 5, 2, 30, tzinfo=timezone.utc),
        deposit_date=datetime(2024, 1, 6, 10, 5, tzinfo=timezone.utc),
        deposit_amount_cents=10150,
        short_name_id=short_name_1.id,
    ).save()

    EFTCreditModel(
        eft_file_id=eft_file.id,
        short_name_id=s1_transaction1.short_name_id,
        amount=s1_transaction1.deposit_amount_cents / 100,
        remaining_amount=s1_transaction1.deposit_amount_cents / 100,
    ).save()

    # Identical to transaction 1 should not return duplicate short name rows - partitioned by transaction date, id
    s1_transaction2: EFTTransactionModel = EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 5, 2, 30, tzinfo=timezone.utc),
        deposit_date=datetime(2024, 1, 6, 10, 5, tzinfo=timezone.utc),
        deposit_amount_cents=10250,
        short_name_id=short_name_1.id,
    ).save()

    EFTCreditModel(
        eft_file_id=eft_file.id,
        short_name_id=s1_transaction2.short_name_id,
        amount=s1_transaction2.deposit_amount_cents / 100,
        remaining_amount=s1_transaction2.deposit_amount_cents / 100,
    ).save()

    EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 10, 2, 30, tzinfo=timezone.utc),
        deposit_date=datetime(2024, 1, 5, 10, 5, tzinfo=timezone.utc),
        deposit_amount_cents=30150,
        short_name_id=short_name_1.id,
    ).save()

    # short_name_2 transactions - to test date filters
    s2_transaction1: EFTTransactionModel = EFTTransactionModel(
        line_type=EFTFileLineType.TRANSACTION.value,
        line_number=1,
        file_id=eft_file.id,
        status_code=EFTProcessStatus.COMPLETED.value,
        transaction_date=datetime(2024, 1, 15, 2, 30, tzinfo=timezone.utc),
        deposit_date=datetime(2024, 1, 16, 8, 0, tzinfo=timezone.utc),
        deposit_amount_cents=30250,
        short_name_id=short_name_2.id,
    ).save()

    EFTCreditModel(
        eft_file_id=eft_file.id,
        short_name_id=s2_transaction1.short_name_id,
        amount=s2_transaction1.deposit_amount_cents / 100,
        remaining_amount=s2_transaction1.deposit_amount_cents / 100,
    ).save()

    s1_refund = EFTRefundModel(
        short_name_id=short_name_1.id,
        refund_amount=100.00,
        cas_supplier_number="123",
        cas_supplier_site="123",
        refund_email="test@example.com",
        comment="Test comment",
        status=EFTShortnameRefundStatus.PENDING_APPROVAL.value,
    ).save()

    return short_name_1, s1_transaction1, short_name_2, s2_transaction1, s1_refund


def create_eft_search_data():
    """Create seed data for EFT searches."""
    payment_account_1 = factory_payment_account(
        payment_method_code=PaymentMethod.EFT.value,
        auth_account_id="1111",
        name="ABC-1111",
        branch_name="111",
    ).save()
    payment_account_2 = factory_payment_account(
        payment_method_code=PaymentMethod.EFT.value,
        auth_account_id="2222",
        name="DEF-2222",
        branch_name="222",
    ).save()
    payment_account_3 = factory_payment_account(
        payment_method_code=PaymentMethod.EFT.value,
        auth_account_id="3333",
        name="GHI-3333",
        branch_name="333",
    ).save()

    # Create unlinked short name
    short_name_unlinked = factory_eft_shortname(short_name="TESTSHORTNAME1").save()

    # Create single linked short name
    short_name_linked = factory_eft_shortname(
        short_name="TESTSHORTNAME2", short_name_type=EFTShortnameType.WIRE.value
    ).save()
    factory_eft_shortname_link(
        short_name_id=short_name_linked.id,
        auth_account_id=payment_account_1.auth_account_id,
        updated_by="IDIR/JSMITH",
    ).save()
    # Create statement with multiple invoices
    s1_invoice_1 = factory_invoice(
        payment_account_1, payment_method_code=PaymentMethod.EFT.value, total=50, paid=0
    ).save()
    s1_invoice_2 = factory_invoice(
        payment_account_1,
        payment_method_code=PaymentMethod.EFT.value,
        total=100.50,
        paid=0,
    ).save()
    s1_settings = factory_statement_settings(
        payment_account_id=payment_account_1.id,
        frequency=StatementFrequency.MONTHLY.value,
    )
    statement_1 = factory_statement(
        payment_account_id=payment_account_1.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=s1_settings.id,
    )
    factory_statement_invoices(statement_id=statement_1.id, invoice_id=s1_invoice_1.id)
    factory_statement_invoices(statement_id=statement_1.id, invoice_id=s1_invoice_2.id)

    # Create multi account linked short name
    short_name_multi_linked = factory_eft_shortname(short_name="TESTSHORTNAME3").save()
    factory_eft_shortname_link(
        short_name_id=short_name_multi_linked.id,
        auth_account_id=payment_account_2.auth_account_id,
        updated_by="IDIR/JSMITH",
    ).save()
    factory_eft_shortname_link(
        short_name_id=short_name_multi_linked.id,
        auth_account_id=payment_account_3.auth_account_id,
        updated_by="IDIR/JSMITH",
    ).save()

    s2_settings = factory_statement_settings(
        payment_account_id=payment_account_2.id,
        frequency=StatementFrequency.MONTHLY.value,
    )
    statement_2 = factory_statement(
        payment_account_id=payment_account_2.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=s2_settings.id,
    )

    s3_settings = factory_statement_settings(
        payment_account_id=payment_account_3.id,
        frequency=StatementFrequency.MONTHLY.value,
    )
    statement_3 = factory_statement(
        payment_account_id=payment_account_3.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=s3_settings.id,
    )
    s3_invoice_1 = factory_invoice(
        payment_account_3,
        payment_method_code=PaymentMethod.EFT.value,
        total=33.33,
        paid=0,
    ).save()
    factory_statement_invoices(statement_id=statement_3.id, invoice_id=s3_invoice_1.id)

    return {
        "single-linked": {
            "short_name": short_name_linked,
            "accounts": [payment_account_1],
            "statement_summary": [{"statement_id": statement_1.id, "owing_amount": 150.50}],
        },
        "multi-linked": {
            "short_name": short_name_multi_linked,
            "accounts": [payment_account_2, payment_account_3],
            "statement_summary": [
                {"statement_id": statement_2.id, "owing_amount": 0},
                {"statement_id": statement_3.id, "owing_amount": 33.33},
            ],
        },
        "unlinked": {
            "short_name": short_name_unlinked,
            "accounts": [],
            "statement_summary": None,
        },
    }


def assert_short_name(
    result_dict: dict,
    short_name: EFTShortnamesModel,
    payment_account: PaymentAccountModel = None,
    statement_summary=None,
):
    """Assert short name result."""
    assert result_dict["shortName"] == short_name.short_name
    assert result_dict["shortNameType"] == short_name.type

    if not payment_account:
        assert result_dict["accountId"] is None
        assert result_dict["accountName"] is None
        assert result_dict["accountBranch"] is None
    else:
        assert result_dict["accountId"] == payment_account.auth_account_id
        assert payment_account.name.startswith(result_dict["accountName"])
        assert result_dict["accountBranch"] == payment_account.branch_name

    if not statement_summary:
        assert result_dict["amountOwing"] == 0
        assert result_dict["statementId"] is None
    else:
        assert result_dict["amountOwing"] == statement_summary["owing_amount"]
        assert result_dict["statementId"] == statement_summary["statement_id"]


def test_search_eft_short_names(session, client, jwt, app):
    """Assert that EFT short names can be searched."""
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    # Assert initial search returns empty items
    rv = client.get("/api/v1/eft-shortnames", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 0

    # create test data
    data_dict = create_eft_search_data()

    # Assert statement id
    target_statement_id = data_dict["single-linked"]["statement_summary"][0]["statement_id"]
    rv = client.get(f"/api/v1/eft-shortnames?statementId={target_statement_id}", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 3
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert_short_name(
        result_dict["items"][0],
        data_dict["single-linked"]["short_name"],
        data_dict["single-linked"]["accounts"][0],
        data_dict["single-linked"]["statement_summary"][0],
    )

    # Assert amount owing
    rv = client.get("/api/v1/eft-shortnames?amountOwing=33.33", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 3
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert result_dict["items"][0]["shortName"] == "TESTSHORTNAME3"
    assert_short_name(
        result_dict["items"][0],
        data_dict["multi-linked"]["short_name"],
        data_dict["multi-linked"]["accounts"][1],
        data_dict["multi-linked"]["statement_summary"][1],
    )

    # Assert search returns unlinked short names
    rv = client.get("/api/v1/eft-shortnames?state=UNLINKED", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 1
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert result_dict["items"][0]["shortName"] == "TESTSHORTNAME1"
    assert_short_name(result_dict["items"][0], data_dict["unlinked"]["short_name"])

    # Assert search returns linked short names with payment account name that has a branch
    rv = client.get("/api/v1/eft-shortnames?state=LINKED", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 3
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 3
    assert_short_name(
        result_dict["items"][0],
        data_dict["single-linked"]["short_name"],
        data_dict["single-linked"]["accounts"][0],
        data_dict["single-linked"]["statement_summary"][0],
    )
    assert_short_name(
        result_dict["items"][1],
        data_dict["multi-linked"]["short_name"],
        data_dict["multi-linked"]["accounts"][0],
        None,
    )  # None because we don't return a statement id if there are no invoices associated.
    assert_short_name(
        result_dict["items"][2],
        data_dict["multi-linked"]["short_name"],
        data_dict["multi-linked"]["accounts"][1],
        data_dict["multi-linked"]["statement_summary"][1],
    )

    # Assert search account name
    rv = client.get("/api/v1/eft-shortnames?state=LINKED&accountName=BC", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name(
        result_dict["items"][0],
        data_dict["single-linked"]["short_name"],
        data_dict["single-linked"]["accounts"][0],
        data_dict["single-linked"]["statement_summary"][0],
    )

    # Assert search account branch
    rv = client.get("/api/v1/eft-shortnames?state=LINKED&accountBranch=2", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name(
        result_dict["items"][0],
        data_dict["multi-linked"]["short_name"],
        data_dict["multi-linked"]["accounts"][0],
        None,
    )

    # Assert search query by no state will return all records
    rv = client.get("/api/v1/eft-shortnames", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 3
    assert result_dict["total"] == 4
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 4
    assert_short_name(result_dict["items"][0], data_dict["unlinked"]["short_name"])
    assert_short_name(
        result_dict["items"][1],
        data_dict["single-linked"]["short_name"],
        data_dict["single-linked"]["accounts"][0],
        data_dict["single-linked"]["statement_summary"][0],
    )
    assert_short_name(
        result_dict["items"][2],
        data_dict["multi-linked"]["short_name"],
        data_dict["multi-linked"]["accounts"][0],
        None,
    )
    assert_short_name(
        result_dict["items"][3],
        data_dict["multi-linked"]["short_name"],
        data_dict["multi-linked"]["accounts"][1],
        data_dict["multi-linked"]["statement_summary"][1],
    )

    # Assert search pagination - page 1 works
    rv = client.get("/api/v1/eft-shortnames?page=1&limit=1", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 3
    assert result_dict["total"] == 4
    assert result_dict["limit"] == 1
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name(result_dict["items"][0], data_dict["unlinked"]["short_name"])

    # Assert search pagination - page 2 works
    rv = client.get("/api/v1/eft-shortnames?page=2&limit=1", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 2
    assert result_dict["stateTotal"] == 3
    assert result_dict["total"] == 4
    assert result_dict["limit"] == 1
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name(
        result_dict["items"][0],
        data_dict["single-linked"]["short_name"],
        data_dict["single-linked"]["accounts"][0],
        data_dict["single-linked"]["statement_summary"][0],
    )

    # Assert search text brings back one short name
    rv = client.get("/api/v1/eft-shortnames?shortName=name1", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 3
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name(result_dict["items"][0], data_dict["unlinked"]["short_name"])

    # Assert search account id
    rv = client.get("/api/v1/eft-shortnames?state=LINKED&accountId=1111", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name(
        result_dict["items"][0],
        data_dict["single-linked"]["short_name"],
        data_dict["single-linked"]["accounts"][0],
        data_dict["single-linked"]["statement_summary"][0],
    )

    # Assert search account id list
    rv = client.get("/api/v1/eft-shortnames?state=LINKED&accountIdList=1111,999", headers=headers)
    assert rv.status_code == 200

    result_dict = rv.json
    assert result_dict is not None
    assert result_dict["page"] == 1
    assert result_dict["stateTotal"] == 2
    assert result_dict["total"] == 1
    assert result_dict["limit"] == 10
    assert result_dict["items"] is not None
    assert len(result_dict["items"]) == 1
    assert_short_name(
        result_dict["items"][0],
        data_dict["single-linked"]["short_name"],
        data_dict["single-linked"]["accounts"][0],
        data_dict["single-linked"]["statement_summary"][0],
    )


@pytest.mark.parametrize(
    "test_name, payload",
    [
        (
            "create_refund_cheque",
            EFTShortNameRefundPostRequest(
                short_name_id=0,
                refund_amount=100.00,
                refund_email="test@example.com",
                comment="Refund for overpayment",
                refund_method=APRefundMethod.CHEQUE.value,
                entity_name="Test Entity",
                street="123 Test St",
                street_additional="Suite 100",
                city="Victoria",
                region="BC",
                country="CA",
                postal_code="V8V 1V1",
                delivery_instructions="Leave at front door",
            ),
        ),
        (
            "create_refund_eft",
            EFTShortNameRefundPostRequest(
                short_name_id=0,
                refund_amount=100.00,
                refund_email="test@example.com",
                comment="Refund for overpayment",
                refund_method=APRefundMethod.EFT.value,
                cas_supplier_number="CAS123",
                cas_supplier_site="123",
            ),
        ),
        (
            "invalid_refund_eft",
            EFTShortNameRefundPostRequest(
                short_name_id=0,
                refund_amount=100.00,
                refund_email="test@example.com",
                comment="Refund for overpayment",
                refund_method=APRefundMethod.EFT.value,
                # Missing CAS details.
            ),
        ),
        (
            "invalid_refund_cheque",
            EFTShortNameRefundPostRequest(
                short_name_id=0,
                refund_amount=100.00,
                refund_email="test@example.com",
                comment="Refund for overpayment",
                refund_method=APRefundMethod.CHEQUE.value,
                # Missing Address details
            ),
        ),
    ],
)
def test_post_shortname_refund(db, session, client, jwt, emails_with_keycloak_role_mock, test_name, payload):
    """Test successful creation of a shortname refund."""
    token = jwt.create_jwt(get_claims(roles=[Role.EFT_REFUND.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    payment_account = factory_payment_account(
        payment_method_code=PaymentMethod.EFT.value, auth_account_id="1234"
    ).save()
    eft_file = factory_eft_file().save()
    short_name = factory_eft_shortname(short_name="TESTSHORTNAME").save()
    factory_eft_credit(
        eft_file_id=eft_file.id,
        short_name_id=short_name.id,
        amount=100,
        remaining_amount=100,
    ).save()

    data = payload.to_dict()
    data.update(
        {
            "shortNameId": short_name.id,
            "authAccountId": payment_account.auth_account_id,
        }
    )
    with patch("pay_api.services.eft_refund.send_email") as mock_email:
        rv = client.post("/api/v1/eft-shortnames/shortname-refund", headers=headers, json=data)
        if "invalid" in test_name:
            assert rv.status_code == 400
            assert Error.INVALID_REFUND.value in rv.json["type"]
            return
        assert rv.status_code == 202
        mock_email.assert_called_once()

    eft_refund = db.session.query(EFTRefundModel).one_or_none()
    assert eft_refund.id is not None
    assert eft_refund.short_name_id == short_name.id
    assert eft_refund.refund_amount == payload.refund_amount

    assert eft_refund.refund_email == payload.refund_email
    assert eft_refund.comment == payload.comment
    assert eft_refund.status == EFTShortnameRefundStatus.PENDING_APPROVAL.value

    if eft_refund.refund_method == APRefundMethod.CHEQUE.value:
        assert eft_refund.entity_name == payload.entity_name
        assert eft_refund.street == payload.street
        assert eft_refund.street_additional == payload.street_additional
        assert eft_refund.city == payload.city
        assert eft_refund.region == payload.region
        assert eft_refund.country == payload.country
        assert eft_refund.postal_code == payload.postal_code
        assert eft_refund.delivery_instructions == payload.delivery_instructions
    else:
        assert eft_refund.cas_supplier_number == payload.cas_supplier_number
        assert eft_refund.cas_supplier_site == payload.cas_supplier_site

    history_record = db.session.query(EFTShortnamesHistoryModel).one_or_none()
    assert history_record is not None
    assert history_record.amount == 100
    assert history_record.eft_refund_id == eft_refund.id
    assert history_record.credit_balance == 0
    assert history_record.transaction_type == EFTHistoricalTypes.SN_REFUND_PENDING_APPROVAL.value


def test_post_shortname_refund_invalid_request(client, mocker, jwt):
    """Test handling of invalid request format."""
    data = {"invalid_field": "invalid_value"}
    token = jwt.create_jwt(get_claims(roles=[Role.EFT_REFUND.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.post("/api/v1/eft-shortnames/shortname-refund", headers=headers, json=data)

    assert rv.status_code == 400
    assert "INVALID_REQUEST" in rv.json["type"]


@pytest.mark.parametrize(
    "query_string_factory, test_name, count",
    [
        (lambda short_id: "", "get_all", 3),
        (
            lambda short_id: f"?short_name_id={short_id}&statuses={EFTShortnameRefundStatus.APPROVED.value},"
            f"{EFTShortnameRefundStatus.PENDING_APPROVAL.value}",
            "short_name_id_status_filter_multiple",
            2,
        ),
        (
            lambda short_id: f"?short_name_id={short_id}&statuses={EFTShortnameRefundStatus.DECLINED.value}",
            "short_name_id_status_filter_rejected",
            1,
        ),
        (
            lambda short_id: f"?statuses={EFTShortnameRefundStatus.APPROVED.value},"
            f"{EFTShortnameRefundStatus.PENDING_APPROVAL.value}",
            "status_filter_multiple",
            2,
        ),
        (
            lambda short_id: f"?statuses={EFTShortnameRefundStatus.DECLINED.value}",
            "status_filter_rejected",
            1,
        ),
    ],
)
def test_get_shortname_refund(session, client, jwt, query_string_factory, test_name, count):
    """Test get short name refund."""
    short_name = factory_eft_shortname("TEST_SHORTNAME").save()
    query_string = query_string_factory(short_name.id)
    factory_eft_refund(short_name_id=short_name.id, status=EFTShortnameRefundStatus.APPROVED.value)
    factory_eft_refund(
        short_name_id=short_name.id,
        status=EFTShortnameRefundStatus.PENDING_APPROVAL.value,
    )
    factory_eft_refund(short_name_id=short_name.id, status=EFTShortnameRefundStatus.DECLINED.value)
    token = jwt.create_jwt(get_claims(roles=[Role.EFT_REFUND.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.get(f"/api/v1/eft-shortnames/shortname-refund{query_string}", headers=headers)
    assert rv.status_code == 200
    assert len(rv.json) == count


@pytest.mark.parametrize(
    "test_name, payload, role",
    [
        (
            "forbidden_approved_refund",
            EFTShortNameRefundPatchRequest(
                comment="Test comment",
                decline_reason="Test reason",
                status=EFTShortnameRefundStatus.APPROVED.value,
            ).to_dict(),
            Role.EFT_REFUND_APPROVER.value,
        ),
        (
            "valid_approved_refund",
            EFTShortNameRefundPatchRequest(
                comment="Test comment", decline_reason="Test reason", status=EFTShortnameRefundStatus.APPROVED.value
            ).to_dict(),
            Role.EFT_REFUND_APPROVER.value,
        ),
        (
            "valid_rejected_refund_and_cheque_status",
            EFTShortNameRefundPatchRequest(
                comment="Test comment",
                decline_reason="Test reason",
                status=EFTShortnameRefundStatus.DECLINED.value,
                cheque_status=ChequeRefundStatus.CHEQUE_UNDELIVERABLE.value,
            ).to_dict(),
            Role.EFT_REFUND_APPROVER.value,
        ),
        ("unauthorized", {}, Role.EFT_REFUND.value),
        (
            "bad_transition",
            EFTShortNameRefundPatchRequest(
                comment="Test comment",
                decline_reason="Test reason",
                status=EFTShortnameRefundStatus.PENDING_APPROVAL.value,
            ).to_dict(),
            Role.EFT_REFUND_APPROVER.value,
        ),
    ],
)
def test_patch_shortname_refund(
    session,
    client,
    jwt,
    payload,
    test_name,
    role,
    send_email_mock,
    emails_with_keycloak_role_mock,
):
    """Test patch short name refund."""
    short_name = factory_eft_shortname("TEST_SHORTNAME").save()
    refund = factory_eft_refund(
        short_name_id=short_name.id,
        refund_amount=10,
        status=EFTShortnameRefundStatus.PENDING_APPROVAL.value,
    )
    eft_file = factory_eft_file().save()
    eft_credit = EFTCreditModel(
        eft_file_id=eft_file.id,
        short_name_id=short_name.id,
        amount=100,
        remaining_amount=90,
    ).save()
    eft_history = factory_eft_history(short_name.id, refund.id, 10, 10)
    user_name = "TEST_USER"
    if test_name == "bad_transition":
        refund.status = EFTShortnameRefundStatus.APPROVED.value
        refund.save()
    elif test_name == "valid_approved_refund":
        refund.created_by = "OTHER_USER"
        refund.save()

    token = jwt.create_jwt(get_claims(roles=[role], username=user_name), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.patch(
        f"/api/v1/eft-shortnames/shortname-refund/{refund.id}",
        headers=headers,
        json=payload,
    )
    match test_name:
        case "forbidden_approved_refund":
            assert rv.status_code == 403
        case "unauthorized":
            assert rv.status_code == 401
        case "bad_transition" | "invalid_patch_refund":
            assert rv.status_code == 400
            assert "REFUND_ALREADY_FINALIZED" in rv.json["type"]
        case "valid_approved_refund":
            assert rv.status_code == 200
            assert rv.json["status"] == EFTShortnameRefundStatus.APPROVED.value
            assert rv.json["comment"] == "Test comment"
            assert eft_history.transaction_type == EFTHistoricalTypes.SN_REFUND_APPROVED.value
        case "valid_rejected_refund_and_cheque_status":
            assert rv.status_code == 200
            assert rv.json["status"] == EFTShortnameRefundStatus.DECLINED.value
            assert rv.json["comment"] == "Test comment"
            assert rv.json["chequeStatus"] == ChequeRefundStatus.CHEQUE_UNDELIVERABLE.value
            history = EFTShortnamesHistoryModel.find_by_eft_refund_id(refund.id)[0]
            assert history
            assert history.credit_balance == 90 + 10
            assert history.transaction_type == EFTHistoricalTypes.SN_REFUND_DECLINED.value
            eft_credit = EFTCreditModel.find_by_id(eft_credit.id)
            assert eft_credit.remaining_amount == 90 + 10
            assert rv.json["declineReason"]
        case _:
            raise ValueError(f"Invalid test case {test_name}")


def test_patch_shortname(session, client, jwt):
    """Test patch EFT Short name."""
    data = {"email": "invalid_email", "casSupplierNumber": "1234567ABC", "casSupplierSite": "1234567ABC"}

    short_name = factory_eft_shortname("TEST_SHORTNAME").save()
    token = jwt.create_jwt(get_claims(roles=[Role.MANAGE_EFT.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}

    rv = client.patch(f"/api/v1/eft-shortnames/{short_name.id}", headers=headers, json=data)

    assert rv.status_code == 400
    assert "INVALID_REQUEST" in rv.json["type"], "Expecting invalid email format."

    data["email"] = "test@test.com"
    rv = client.patch(f"/api/v1/eft-shortnames/{short_name.id}", headers=headers, json=data)

    assert rv.status_code == 200
    result = rv.json
    assert result is not None
    assert result["casSupplierNumber"] == data["casSupplierNumber"]
    assert result["casSupplierSite"] == data["casSupplierSite"]
    assert result["email"] == data["email"]


def test_get_refund_by_id(session, client, jwt):
    """Test get refund by id."""
    short_name = factory_eft_shortname("TEST_SHORTNAME").save()
    refund = factory_eft_refund(
        short_name_id=short_name.id,
        refund_amount=10,
        status=EFTShortnameRefundStatus.PENDING_APPROVAL.value,
        decline_reason="sucks",
    )
    token = jwt.create_jwt(get_claims(roles=[Role.EFT_REFUND_APPROVER.value]), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.get(f"/api/v1/eft-shortnames/shortname-refund/{refund.id}", headers=headers)
    assert rv.status_code == 200
    assert rv.json["comment"] == refund.comment
    assert rv.json["status"] == refund.status
    assert rv.json["refundAmount"] == refund.refund_amount
    assert rv.json["casSupplierNumber"] == refund.cas_supplier_number
    assert rv.json["casSupplierSite"] == refund.cas_supplier_site
    assert rv.json["refundEmail"] == refund.refund_email
    assert rv.json["shortNameId"] == refund.short_name_id
    assert rv.json["declineReason"] == refund.decline_reason
