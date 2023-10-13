# Copyright © 2019 Province of British Columbia
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

from datetime import datetime
from typing import Dict

from flask import current_app
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Statement as StatementModel
from pay_api.services.queue_publisher import publish_response
from sentry_sdk import capture_message


def publish_mailer_events(message_type: str, pay_account: PaymentAccountModel,
                                additional_params: Dict = {}):
    """Publish payment message to the mailer queue."""
    # Publish message to the Queue, saying account has been activated. Using the event spec.

    fee_schedule: FeeScheduleModel = FeeScheduleModel.find_by_filing_type_and_corp_type(corp_type_code='BCR',
                                                                                        filing_type_code='NSF')

    payload = {
        'specversion': '1.x-wip',
        'type': f'bc.registry.payment.{message_type}',
        'source': f'https://api.pay.bcregistry.gov.bc.ca/v1/accounts/{pay_account.auth_account_id}',
        'id': f'{pay_account.auth_account_id}',
        'time': f'{datetime.now()}',
        'datacontenttype': 'application/json',
        'data': {
            'accountId': pay_account.auth_account_id,
            'nsfFee': float(fee_schedule.fee.amount),
            **additional_params
        }
    }
    try:
        publish_response(payload=payload,
                      client_name=current_app.config.get('NATS_MAILER_CLIENT_NAME'),
                      subject=current_app.config.get('NATS_MAILER_SUBJECT'))
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
    payload = {
        'specversion': '1.x-wip',
        'type': f'bc.registry.payment.statementNotification',
        'source': f'https://api.pay.bcregistry.gov.bc.ca/v1/accounts/{pay_account.auth_account_id}',
        'id': f'{pay_account.auth_account_id}',
        'time': f'{datetime.now()}',
        'datacontenttype': 'application/json',
        'data': {
            'emailAddresses': emails,
            'accountId': pay_account.auth_account_id,
            'fromDate': f'{statement.from_date}',
            'toDate:': f'{statement.to_date}',
            'statementFrequency': statement.frequency,
            'totalAmountOwing': total_amount_owing
        }
    }
    try:
        publish_response(payload=payload,
                         client_name=current_app.config.get('NATS_MAILER_CLIENT_NAME'),
                         subject=current_app.config.get('NATS_MAILER_SUBJECT'))
    except Exception as e:  # pylint: disable=broad-except
        current_app.logger.error(e)
        current_app.logger.warning('Notification to Queue failed for the Account Mailer %s - %s',
                                   pay_account.auth_account_id,
                                   payload)
        capture_message('Notification to Queue failed for the Account Mailer {auth_account_id}, {msg}.'.format(
            auth_account_id=pay_account.auth_account_id, msg=payload), level='error')

        return False

    return True

