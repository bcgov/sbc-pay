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

"""Tests to assure the EFTOverpaymentNotificationTask.

Test-Suite to ensure that the EFTOverpaymentNotificationTask is working as expected.
"""
from datetime import datetime, timedelta
from unittest.mock import ANY, call, patch

import pytest
from freezegun import freeze_time
from pay_api.utils.enums import EFTShortnameStatus

from tasks.eft_overpayment_notification_task import EFTOverpaymentNotificationTask

from .factory import (
    factory_create_eft_credit,
    factory_create_eft_file,
    factory_create_eft_shortname,
    factory_create_eft_transaction,
    factory_eft_shortname_link,
)


def create_unlinked_short_names_data(created_on: datetime):
    """Create seed data for unlinked short names."""
    eft_file = factory_create_eft_file()
    eft_transaction = factory_create_eft_transaction(file_id=eft_file.id)
    unlinked_with_credit = factory_create_eft_shortname("UNLINKED_WITH_CREDIT")
    unlinked_with_credit.created_on = created_on
    unlinked_with_credit.save()
    factory_create_eft_credit(
        short_name_id=unlinked_with_credit.id,
        eft_transaction_id=eft_transaction.id,
        eft_file_id=eft_file.id,
        amount=100,
        remaining_amount=100,
    )

    inactive_link_with_credit = factory_create_eft_shortname("INACTIVE_LINK_WITH_CREDIT")
    inactive_link_with_credit.created_on = created_on
    inactive_link_with_credit.save()
    factory_create_eft_credit(
        short_name_id=inactive_link_with_credit.id,
        eft_transaction_id=eft_transaction.id,
        eft_file_id=eft_file.id,
        amount=10,
        remaining_amount=10,
    )
    factory_eft_shortname_link(
        short_name_id=inactive_link_with_credit.id,
        status_code=EFTShortnameStatus.INACTIVE.value,
    )

    # Create unlinked short name that is not 30 days old yet
    unlinked_not_included = factory_create_eft_shortname("UNLINKED_NOT_INCLUDED")
    unlinked_not_included.created_on = created_on + timedelta(days=1)
    unlinked_not_included.save()
    factory_create_eft_credit(
        short_name_id=unlinked_not_included.id,
        eft_transaction_id=eft_transaction.id,
        eft_file_id=eft_file.id,
        amount=100,
        remaining_amount=100,
    )

    return unlinked_with_credit, inactive_link_with_credit, unlinked_not_included


def create_linked_short_names_data(created_on: datetime):
    """Create seed data for linked short names."""
    eft_file = factory_create_eft_file()
    eft_transaction = factory_create_eft_transaction(file_id=eft_file.id)
    linked_with_credit = factory_create_eft_shortname("LINKED_WITH_CREDIT")
    credit_1 = factory_create_eft_credit(
        short_name_id=linked_with_credit.id,
        eft_transaction_id=eft_transaction.id,
        eft_file_id=eft_file.id,
        amount=100,
        remaining_amount=100,
    )
    credit_1.created_on = created_on
    credit_1.save()
    factory_eft_shortname_link(short_name_id=linked_with_credit.id)

    linked_with_no_credit = factory_create_eft_shortname("LINKED_WITH_NO_CREDIT")
    credit_2 = factory_create_eft_credit(
        short_name_id=linked_with_no_credit.id,
        eft_transaction_id=eft_transaction.id,
        eft_file_id=eft_file.id,
        amount=100,
        remaining_amount=0,
    )
    credit_2.created_on = created_on
    credit_2.save()
    factory_eft_shortname_link(short_name_id=linked_with_no_credit.id)
    return linked_with_credit, linked_with_no_credit


def test_over_payment_notification_not_sent(session):
    """Assert notification is not being sent."""
    with patch("tasks.eft_overpayment_notification_task.send_email") as mock_mailer:
        EFTOverpaymentNotificationTask.process_overpayment_notification()
        mock_mailer.assert_not_called()


@pytest.mark.parametrize(
    "test_name, created_on_date, execution_date, assert_calls_override",
    [
        ("has-notifications", datetime(2024, 10, 1, 5), datetime(2024, 10, 2, 5), []),
        ("no-notifications", datetime(2024, 10, 1, 5), datetime(2024, 10, 31, 5), None),
    ],
)
def test_over_payment_notification_unlinked(
    session,
    test_name,
    created_on_date,
    execution_date,
    assert_calls_override,
    emails_with_keycloak_role_mock,
    send_email_mock,
):
    """Assert notification is being sent for unlinked accounts."""
    unlinked_shortname, inactive_link_shortname, _ = create_unlinked_short_names_data(created_on_date)
    expected_email = "test@email.com"
    expected_subject = "Pending Unsettled Amount for Short Name"
    with freeze_time(execution_date):
        EFTOverpaymentNotificationTask.process_overpayment_notification()
        expected_calls = (
            [
                call(
                    recipients=expected_email,
                    subject=f"{expected_subject} {unlinked_shortname.short_name}",
                    body=ANY,
                ),
                call(
                    recipients=expected_email,
                    subject=f"{expected_subject} {inactive_link_shortname.short_name}",
                    body=ANY,
                ),
            ]
            if assert_calls_override is None
            else []
        )
    send_email_mock.assert_has_calls(expected_calls, any_order=True)
    assert send_email_mock.call_count == len(expected_calls)


def test_over_payment_notification_linked(session, emails_with_keycloak_role_mock, send_email_mock):
    """Assert notification is being sent for linked accounts."""
    linked_shortname, _ = create_linked_short_names_data(datetime(2024, 10, 1, 5))
    expected_email = "test@email.com"
    expected_subject = "Pending Unsettled Amount for Short Name"
    with freeze_time(datetime(2024, 10, 1, 7)):
        EFTOverpaymentNotificationTask.process_overpayment_notification()
        expected_calls = [
            call(
                recipients=expected_email,
                subject=f"{expected_subject} {linked_shortname.short_name}",
                body=ANY,
            ),
        ]
    send_email_mock.assert_has_calls(expected_calls, any_order=True)
    assert send_email_mock.call_count == len(expected_calls)


def test_over_payment_notification_override(session, emails_with_keycloak_role_mock, send_email_mock):
    """Assert notification is being sent with date override."""
    linked_shortname, _ = create_linked_short_names_data(datetime(2024, 10, 1, 5))
    expected_email = "test@email.com"
    expected_subject = "Pending Unsettled Amount for Short Name"
    EFTOverpaymentNotificationTask.process_overpayment_notification(date_override="2024-10-01")
    expected_calls = [
        call(
            recipients=expected_email,
            subject=f"{expected_subject} {linked_shortname.short_name}",
            body=ANY,
        ),
    ]
    send_email_mock.assert_has_calls(expected_calls, any_order=True)
    assert send_email_mock.call_count == len(expected_calls)
