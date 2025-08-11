# Copyright © 2022 Province of British Columbia
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

"""Test for the statement receipients service.

Test-Suite to ensure that the Statement Receipients Service is working as expected.
"""
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models.statement_recipients import StatementRecipients as StatementRecipientsModel
from pay_api.services.statement_recipients import StatementRecipients as StatementRecipientsService


def test_statement_recipients_find_statement_notification(session):
    """Assert that a statement notification can be found."""
    payment_account = PaymentAccountModel(auth_account_id="1").save()
    StatementRecipientsModel(
        auth_user_id=1,
        firstname="first",
        lastname="last",
        email="email",
        payment_account_id=payment_account.id,
    ).save()
    statement_notification = StatementRecipientsService().find_statement_notification_details("1")
    assert statement_notification
    assert statement_notification["recipients"]
    assert statement_notification["recipients"][0]["auth_user_id"] == 1
    assert statement_notification["recipients"][0]["firstname"] == "first"
    assert statement_notification["recipients"][0]["lastname"] == "last"
    assert statement_notification["recipients"][0]["email"] == "email"


def test_update_statement_notification_details(session):
    """Assert that a statement notification can be updated."""
    notification_details = {
        "recipients": [
            {
                "authUserId": "987",
                "firstname": "first",
                "lastname": "last",
                "email": "email",
                "accountName": "farmer",
            }
        ]
    }
    StatementRecipientsService().update_statement_notification_details("987", notification_details=notification_details)
    recipients = StatementRecipientsModel().find_all_recipients("987")
    assert recipients
    assert len(recipients) > 0
    assert str(recipients[0].auth_user_id) == notification_details["recipients"][0]["authUserId"]
    assert recipients[0].firstname == notification_details["recipients"][0]["firstname"]
    assert recipients[0].lastname == notification_details["recipients"][0]["lastname"]
    assert recipients[0].email == notification_details["recipients"][0]["email"]
