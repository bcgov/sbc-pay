# Copyright © 2023 Province of British Columbia
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
"""Task to notify user for any outstanding statement."""
from datetime import timedelta

from flask import current_app
from pay_api.models import db
from pay_api.models.invoice import Invoice as InvoiceModel
from pay_api.models.payment_account import PaymentAccount as PaymentAccountModel
from pay_api.models.statement import Statement as StatementModel
from pay_api.models.statement_recipients import StatementRecipients as StatementRecipientsModel
from pay_api.models.statement_settings import StatementSettings as StatementSettingsModel
from pay_api.services.flags import flags
from pay_api.services.statement import Statement
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, StatementFrequency
from pay_api.utils.util import current_local_time, get_first_and_last_dates_of_month
from sentry_sdk import capture_message
from sqlalchemy import Date

from utils.mailer import publish_payment_notification


class StatementDueTask:
    """Task to notify admin for unpaid statements.

    This is currently for EFT payment method invoices only. This may be expanded to
    PAD and ONLINE BANKING in the future.
    """

    @classmethod
    def process_unpaid_statements(cls):
        """Notify for unpaid statements with an amount owing."""
        eft_enabled = flags.is_on('enable-eft-payment-method', default=False)

        if eft_enabled:
            cls._notify_for_monthly()

            # Set overdue status for invoices
            if current_local_time().date().day == 1:
                cls._update_invoice_overdue_status()

    @classmethod
    def _update_invoice_overdue_status(cls):
        """Update the status of any invoices that are overdue."""
        unpaid_status = (
            InvoiceStatus.SETTLEMENT_SCHEDULED.value, InvoiceStatus.PARTIAL.value, InvoiceStatus.CREATED.value)
        db.session.query(InvoiceModel)\
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value,
                    InvoiceModel.overdue_date.isnot(None),
                    InvoiceModel.overdue_date.cast(Date) <= current_local_time().date(),
                    InvoiceModel.invoice_status_code.in_(unpaid_status))\
            .update({InvoiceModel.invoice_status_code: InvoiceStatus.OVERDUE.value}, synchronize_session='fetch')

        db.session.commit()

    @classmethod
    def _notify_for_monthly(cls):
        """Notify for unpaid monthly statements with an amount owing."""
        # Check if we need to send a notification
        send_notification, is_due, last_day, previous_month = cls.determine_to_notify_and_is_due()

        if send_notification:
            statement_settings = StatementSettingsModel.find_accounts_settings_by_frequency(previous_month,
                                                                                            StatementFrequency.MONTHLY)
            auth_account_ids = [pay_account.auth_account_id for _, pay_account in statement_settings]

            for account_id in auth_account_ids:
                try:
                    # Get the most recent monthly statement
                    statement = cls.find_most_recent_statement(account_id, StatementFrequency.MONTHLY.value)
                    summary = Statement.get_summary(account_id, statement.id)
                    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(statement.payment_account_id)

                    # Send payment notification if payment account is using EFT and there is an amount owing
                    if payment_account.payment_method == PaymentMethod.EFT.value and summary['total_due'] > 0:
                        recipients = StatementRecipientsModel. \
                            find_all_recipients_for_payment_id(statement.payment_account_id)

                        if len(recipients) < 1:
                            current_app.logger.info(f'No recipients found for statement: '
                                                    f'{statement.payment_account_id}.Skipping sending')
                            continue

                        to_emails = ','.join([str(recipient.email) for recipient in recipients])

                        publish_payment_notification(pay_account=payment_account,
                                                     statement=statement,
                                                     is_due=is_due,
                                                     due_date=last_day.date(),
                                                     emails=to_emails)
                except Exception as e:  # NOQA # pylint: disable=broad-except
                    capture_message(
                        f'Error on unpaid statement notification auth_account_id={account_id}, '
                        f'ERROR : {str(e)}', level='error')
                    current_app.logger.error(e)
                    continue

    @classmethod
    def find_most_recent_statement(cls, auth_account_id: str, statement_frequency: str) -> StatementModel:
        """Find all payment and invoices specific to a statement."""
        query = db.session.query(StatementModel) \
            .join(PaymentAccountModel, PaymentAccountModel.auth_account_id == auth_account_id) \
            .filter(StatementModel.frequency == statement_frequency) \
            .order_by(StatementModel.to_date.desc())

        return query.first()

    @classmethod
    def determine_to_notify_and_is_due(cls):
        """Determine whether a statement notification is required and due."""
        now = current_local_time()
        previous_month = now.replace(day=1) - timedelta(days=1)
        send_notification = False
        is_due = False

        # Send payment notification if it is 7 days before the due date or on the due date
        _, last_day = get_first_and_last_dates_of_month(now.month, now.year)
        if last_day.date() == now.date():
            # Last day of the month, send payment due
            send_notification = True
            is_due = True
        elif now.date() == (last_day - timedelta(days=7)).date():
            # 7 days from payment due date, send payment reminder
            send_notification = True
            is_due = False

        return send_notification, is_due, last_day, previous_month
