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
from datetime import datetime, timedelta, timezone

from flask import current_app
from pay_api.models import db
from pay_api.models.cfs_account import CfsAccount as CfsAccountModel
from pay_api.models.invoice import Invoice as InvoiceModel
from pay_api.models.invoice_reference import InvoiceReference as InvoiceReferenceModel
from pay_api.models.non_sufficient_funds import NonSufficientFunds as NonSufficientFundsModel
from pay_api.models.payment_account import PaymentAccount as PaymentAccountModel
from pay_api.models.statement import Statement as StatementModel
from pay_api.models.statement_invoices import StatementInvoices as StatementInvoicesModel
from pay_api.models.statement_recipients import StatementRecipients as StatementRecipientsModel
from pay_api.models.statement_settings import StatementSettings as StatementSettingsModel
from pay_api.services.flags import flags
from pay_api.services import NonSufficientFundsService
from pay_api.services.statement import Statement
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, StatementFrequency
from pay_api.utils.util import current_local_time
from sentry_sdk import capture_message

from utils.auth_event import AuthEvent
from utils.enums import StatementNotificationAction
from utils.mailer import StatementNotificationInfo, publish_payment_notification


class StatementDueTask:   # pylint: disable=too-few-public-methods
    """Task to notify admin for unpaid statements.

    This is currently for EFT payment method invoices only. This may be expanded to
    PAD and ONLINE BANKING in the future.
    """

    unpaid_status = [InvoiceStatus.SETTLEMENT_SCHEDULED.value, InvoiceStatus.PARTIAL.value,
                     InvoiceStatus.CREATED.value]

    @classmethod
    def process_unpaid_statements(cls):
        """Notify for unpaid statements with an amount owing."""
        eft_enabled = flags.is_on('enable-eft-payment-method', default=False)
        if eft_enabled:
            cls._update_invoice_overdue_status()
            cls._notify_for_monthly()

    @classmethod
    def _update_invoice_overdue_status(cls):
        """Update the status of any invoices that are overdue."""
        query = db.session.query(InvoiceModel) \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value,
                    InvoiceModel.overdue_date.isnot(None),
                    InvoiceModel.overdue_date <= datetime.now(tz=timezone.utc),
                    InvoiceModel.invoice_status_code.in_(cls.unpaid_status))
        query.update({InvoiceModel.invoice_status_code: InvoiceStatus.OVERDUE.value}, synchronize_session='fetch')
        db.session.commit()

    @classmethod
    def add_to_non_sufficient_funds(cls, payment_account):
        """Add the invoice to the non sufficient funds table."""
        invoices = db.session.query(InvoiceModel.id, InvoiceReferenceModel.invoice_number) \
            .join(InvoiceReferenceModel, InvoiceReferenceModel.invoice_id == InvoiceModel.id) \
            .filter(InvoiceModel.payment_account_id == payment_account.id,
                    InvoiceModel.invoice_status_code == InvoiceStatus.OVERDUE.value,
                    InvoiceModel.id.notin_(
                        db.session.query(NonSufficientFundsModel.invoice_id)
                    )).distinct().all()
        cfs_account = CfsAccountModel.find_effective_by_payment_method(payment_account.id, PaymentMethod.EFT.value)
        for invoice_tuple in invoices:
            NonSufficientFundsService.save_non_sufficient_funds(invoice_id=invoice_tuple[0],
                                                                invoice_number=invoice_tuple[1],
                                                                cfs_account=cfs_account.cfs_account,
                                                                description='EFT invoice overdue')

    @classmethod
    def _notify_for_monthly(cls):
        """Notify for unpaid monthly statements with an amount owing."""
        previous_month = current_local_time().replace(day=1) - timedelta(days=1)
        statement_settings = StatementSettingsModel.find_accounts_settings_by_frequency(previous_month,
                                                                                        StatementFrequency.MONTHLY)
        eft_payment_accounts = [pay_account for _, pay_account in statement_settings
                                if pay_account.payment_method == PaymentMethod.EFT.value]

        current_app.logger.info(f'Processing {len(eft_payment_accounts)} EFT accounts for monthly reminders.')
        for payment_account in eft_payment_accounts:
            try:
                if not (statement := cls._find_most_recent_statement(
                        payment_account.auth_account_id, StatementFrequency.MONTHLY.value)):
                    continue
                action, due_date = cls._determine_action_and_due_date_by_invoice(statement.id)
                total_due = Statement.get_summary(payment_account.auth_account_id, statement.id)['total_due']
                if action and total_due > 0:
                    if action == StatementNotificationAction.OVERDUE:
                        current_app.logger.info('Freezing payment account id: %s locking auth account id: %s',
                                                payment_account.id, payment_account.auth_account_id)
                        # The locking email is sufficient for overdue, no seperate email required.
                        additional_emails = current_app.config.get('EFT_OVERDUE_NOTIFY_EMAILS')
                        AuthEvent.publish_lock_account_event(payment_account, additional_emails)
                        cls.add_to_non_sufficient_funds(payment_account)
                        statement.overdue_notification_date = datetime.now(tz=timezone.utc)
                        statement.save()
                        continue
                    if emails := cls._determine_recipient_emails(statement):
                        publish_payment_notification(
                            StatementNotificationInfo(auth_account_id=payment_account.auth_account_id,
                                                      statement=statement,
                                                      action=action,
                                                      due_date=due_date,
                                                      emails=emails,
                                                      total_amount_owing=total_due))
            except Exception as e:  # NOQA # pylint: disable=broad-except
                capture_message(
                    f'Error on unpaid statement notification auth_account_id={payment_account.auth_account_id}, '
                    f'ERROR : {str(e)}', level='error')
                current_app.logger.error(
                    f'Error on unpaid statement notification auth_account_id={payment_account.auth_account_id}',
                    exc_info=True)
                continue

    @classmethod
    def _find_most_recent_statement(cls, auth_account_id: str, statement_frequency: str) -> StatementModel:
        """Find all payment and invoices specific to a statement."""
        query = db.session.query(StatementModel) \
            .join(PaymentAccountModel) \
            .filter(PaymentAccountModel.auth_account_id == auth_account_id) \
            .filter(StatementModel.frequency == statement_frequency) \
            .filter(StatementModel.overdue_notification_date.is_(None)) \
            .order_by(StatementModel.to_date.desc())

        return query.first()

    @classmethod
    def _determine_action_and_due_date_by_invoice(cls, statement_id: int):
        """Find the most overdue invoice for a statement and provide an action."""
        invoice = db.session.query(InvoiceModel) \
            .join(StatementInvoicesModel, StatementInvoicesModel.invoice_id == InvoiceModel.id) \
            .filter(StatementInvoicesModel.statement_id == statement_id) \
            .filter(InvoiceModel.overdue_date.isnot(None)) \
            .order_by(InvoiceModel.overdue_date.asc()) \
            .first()

        if invoice is None:
            return None, None

        # 1. EFT Invoice created between or on January 1st <-> January 31st
        # 2. Statement Day Feburary 1st
        # 3. 7 day reminder Feb 21th ( due date - 7)
        # 4. Final reminder Feb 28th (due date client should be told to pay by this time)
        # 5. Overdue Date and account locked March 15th
        day_before_invoice_overdue = (invoice.overdue_date - timedelta(days=1 + 15)).date()
        seven_days_before_invoice_due = day_before_invoice_overdue - timedelta(days=7 + 15)
        now_date = datetime.now(tz=timezone.utc).date()

        if invoice.invoice_status_code == InvoiceStatus.OVERDUE.value:
            return StatementNotificationAction.OVERDUE, day_before_invoice_overdue
        if day_before_invoice_overdue == now_date:
            return StatementNotificationAction.DUE, day_before_invoice_overdue
        if seven_days_before_invoice_due == now_date:
            return StatementNotificationAction.REMINDER, day_before_invoice_overdue
        return None, day_before_invoice_overdue

    @classmethod
    def _determine_recipient_emails(cls, statement: StatementRecipientsModel) -> str:
        if (recipients := StatementRecipientsModel.find_all_recipients_for_payment_id(statement.payment_account_id)):
            recipients = ','.join([str(recipient.email) for recipient in recipients])

            return recipients

        current_app.logger.error(f'No recipients found for statement: {statement.payment_account_id}. Skipping.')
        return None
