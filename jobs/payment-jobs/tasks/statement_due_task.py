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
from pay_api.utils.util import current_local_time, get_local_time
from sentry_sdk import capture_message
from sqlalchemy import func

from utils.mailer import StatementNotificationInfo, publish_payment_notification


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
            cls._update_invoice_overdue_status()

    @classmethod
    def _update_invoice_overdue_status(cls):
        """Update the status of any invoices that are overdue."""
        legislative_timezone = current_app.config.get('LEGISLATIVE_TIMEZONE')
        overdue_datetime = func.timezone(legislative_timezone, func.timezone('UTC', InvoiceModel.overdue_date))

        unpaid_status = (
            InvoiceStatus.SETTLEMENT_SCHEDULED.value, InvoiceStatus.PARTIAL.value, InvoiceStatus.CREATED.value)
        db.session.query(InvoiceModel) \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value,
                    InvoiceModel.overdue_date.isnot(None),
                    func.date(overdue_datetime) <= current_local_time().date(),
                    InvoiceModel.invoice_status_code.in_(unpaid_status))\
            .update({InvoiceModel.invoice_status_code: InvoiceStatus.OVERDUE.value}, synchronize_session='fetch')

        db.session.commit()

    @classmethod
    def _notify_for_monthly(cls):
        """Notify for unpaid monthly statements with an amount owing."""
        previous_month = current_local_time().replace(day=1) - timedelta(days=1)
        statement_settings = StatementSettingsModel.find_accounts_settings_by_frequency(previous_month,
                                                                                        StatementFrequency.MONTHLY)

        # Get EFT auth account ids for statements
        auth_account_ids = [pay_account.auth_account_id for _, pay_account in statement_settings
                            if pay_account.payment_method == PaymentMethod.EFT.value]

        current_app.logger.info(f'Processing {len(auth_account_ids)} EFT accounts for monthly reminders.')

        for account_id in auth_account_ids:
            try:
                # Get the most recent monthly statement
                statement = cls.find_most_recent_statement(account_id, StatementFrequency.MONTHLY.value)
                invoices: [InvoiceModel] = StatementModel.find_all_payments_and_invoices_for_statement(statement.id)
                # check if there is an unpaid statement invoice that requires a reminder
                send_notification, is_due, due_date = cls.determine_to_notify_and_is_due(invoices)

                if send_notification:
                    summary = Statement.get_summary(account_id, statement.id)
                    # Send payment notification if there is an amount owing
                    if summary['total_due'] > 0:
                        recipients = StatementRecipientsModel. \
                            find_all_recipients_for_payment_id(statement.payment_account_id)

                        if len(recipients) < 1:
                            current_app.logger.info(f'No recipients found for statement: '
                                                    f'{statement.payment_account_id}.Skipping sending')
                            continue

                        to_emails = ','.join([str(recipient.email) for recipient in recipients])

                        publish_payment_notification(
                            StatementNotificationInfo(auth_account_id=account_id,
                                                      statement=statement,
                                                      is_due=is_due,
                                                      due_date=due_date,
                                                      emails=to_emails,
                                                      total_amount_owing=summary['total_due']))
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
            .join(PaymentAccountModel) \
            .filter(PaymentAccountModel.auth_account_id == auth_account_id) \
            .filter(StatementModel.frequency == statement_frequency) \
            .order_by(StatementModel.to_date.desc())

        return query.first()

    @classmethod
    def determine_to_notify_and_is_due(cls, invoices: [InvoiceModel]):
        """Determine whether a statement notification is required and due."""
        unpaid_status = [InvoiceStatus.SETTLEMENT_SCHEDULED.value, InvoiceStatus.PARTIAL.value,
                         InvoiceStatus.CREATED.value]
        now = current_local_time().date()
        send_notification = False
        is_due = False
        due_date = None

        invoice: InvoiceModel
        for invoice in invoices:
            if invoice.invoice_status_code not in unpaid_status or invoice.overdue_date is None:
                continue

            invoice_due_date = get_local_time(invoice.overdue_date) \
                .date() - timedelta(days=1)  # Day before invoice overdue date
            invoice_reminder_date = invoice_due_date - timedelta(days=7)  # 7 days before invoice due date

            # Send payment notification if it is 7 days before the overdue date or on the overdue date
            if invoice_due_date == now:
                # due today, send payment due
                send_notification = True
                is_due = True
                due_date = invoice_due_date
                current_app.logger.info(f'Found invoice due: {invoice.id}.')
                break
            if invoice_reminder_date == now:
                # 7 days till due date, send payment reminder
                send_notification = True
                is_due = False
                due_date = invoice_due_date
                current_app.logger.info(f'Found invoice for 7 day reminder: {invoice.id}.')
                break

        return send_notification, is_due, due_date
