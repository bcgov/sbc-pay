# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Task to activate accounts with pending activation.Mostly for PAD with 3 day activation period."""
from dataclasses import dataclass
from datetime import datetime

from flask import current_app
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Statement as StatementModel
from pay_api.services import gcp_queue_publisher
from pay_api.utils.enums import QueueSources
from sbc_common_components.utils.enums import QueueMessageTypes
from sentry_sdk import capture_message

from .enums import StatementNotificationAction


@dataclass
class StatementNotificationInfo:
    """Used for Statement Notifications."""

    auth_account_id: str
    statement: StatementModel
    action: StatementNotificationAction
    due_date: datetime
    emails: str
    total_amount_owing: float


def publish_mailer_events(message_type: str, pay_account: PaymentAccountModel, additional_params=None):
    """Publish payment message to the mailer queue."""
    # Publish message to the Queue, saying account has been activated. Using the event spec.

    fee_schedule: FeeScheduleModel = FeeScheduleModel.find_by_filing_type_and_corp_type(corp_type_code='BCR',
                                                                                        filing_type_code='NSF')
    payload = {
        'accountId': pay_account.auth_account_id,
        'nsfFee': float(fee_schedule.fee.amount),
        **(additional_params or {})
    }
    try:
        gcp_queue_publisher.publish_to_queue(
            gcp_queue_publisher.QueueMessage(
                source=QueueSources.PAY_JOBS.value,
                message_type=message_type,
                payload=payload,
                topic=current_app.config.get('ACCOUNT_MAILER_TOPIC')
            )
        )
    except Exception as e:  # pylint: disable=broad-except
        current_app.logger.error(e)
        current_app.logger.warning('Notification to Queue failed for the Account Mailer %s - %s',
                                   pay_account.auth_account_id,
                                   payload)
        capture_message('Notification to Queue failed for the Account Mailer {auth_account_id}, {msg}.'.format(
            auth_account_id=pay_account.auth_account_id, msg=payload), level='error')


def publish_statement_notification(pay_account: PaymentAccountModel, statement: StatementModel,
                                   total_amount_owing: float, emails: str) -> bool:
    """Publish payment statement notification message to the mailer queue."""
    message_type = QueueMessageTypes.STATEMENT_NOTIFICATION.value
    payload = {
        'emailAddresses': emails,
        'accountId': pay_account.auth_account_id,
        'fromDate': f'{statement.from_date}',
        'toDate': f'{statement.to_date}',
        'statementFrequency': statement.frequency,
        'totalAmountOwing': total_amount_owing
    }
    try:
        gcp_queue_publisher.publish_to_queue(
            gcp_queue_publisher.QueueMessage(
                source=QueueSources.PAY_JOBS.value,
                message_type=message_type,
                payload=payload,
                topic=current_app.config.get('ACCOUNT_MAILER_TOPIC')
            )
        )
    except Exception as e:  # pylint: disable=broad-except
        current_app.logger.error(e)
        current_app.logger.warning('Notification to Queue failed for the Account Mailer %s - %s',
                                   pay_account.auth_account_id,
                                   payload)
        capture_message('Notification to Queue failed for the Account Mailer {auth_account_id}, {msg}.'.format(
            auth_account_id=pay_account.auth_account_id, msg=payload), level='error')

        return False

    return True


def publish_payment_notification(info: StatementNotificationInfo) -> bool:
    """Publish payment notification message to the mailer queue."""
    message_type = QueueMessageTypes.PAYMENT_DUE_NOTIFICATION.value if info.is_due \
        else QueueMessageTypes.PAYMENT_REMINDER_NOTIFICATION.value

    payload = {
        'emailAddresses': info.emails,
        'accountId': info.auth_account_id,
        'dueDate': f'{info.due_date}',
        'statementFrequency': info.statement.frequency,
        'totalAmountOwing': info.total_amount_owing
    }
    try:
        gcp_queue_publisher.publish_to_queue(
            gcp_queue_publisher.QueueMessage(
                source=QueueSources.PAY_JOBS.value,
                message_type=message_type,
                payload=payload,
                topic=current_app.config.get('ACCOUNT_MAILER_TOPIC')
            )
        )
    except Exception as e:  # pylint: disable=broad-except
        current_app.logger.error(e)
        current_app.logger.warning('Notification to Queue failed for the Account Mailer %s - %s',
                                   info.auth_account_id,
                                   payload)
        capture_message('Notification to Queue failed for the Account Mailer {auth_account_id}, {msg}.'.format(
            auth_account_id=info.auth_account_id, msg=payload), level='error')

        return False

    return True
