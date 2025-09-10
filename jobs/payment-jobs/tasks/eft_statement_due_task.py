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
from calendar import monthrange
from datetime import datetime, timedelta, timezone

import pytz
from flask import current_app
from pay_api.models import db
from pay_api.models.cfs_account import CfsAccount as CfsAccountModel
from pay_api.models.eft_short_name_links import EFTShortnameLinks as EFTShortnameLinksModel
from pay_api.models.invoice import Invoice as InvoiceModel
from pay_api.models.invoice_reference import InvoiceReference as InvoiceReferenceModel
from pay_api.models.non_sufficient_funds import NonSufficientFunds as NonSufficientFundsModel
from pay_api.models.payment_account import PaymentAccount as PaymentAccountModel
from pay_api.models.statement import Statement as StatementModel
from pay_api.models.statement_invoices import StatementInvoices as StatementInvoicesModel
from pay_api.models.statement_recipients import StatementRecipients as StatementRecipientsModel
from pay_api.services import NonSufficientFundsService
from pay_api.services.statement import Statement
from pay_api.services.statement_settings import StatementSettings as StatementSettingsService
from pay_api.utils.auth_event import AuthEvent, LockAccountDetails
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, QueueSources, StatementFrequency, SuspensionReasonCodes
from pay_api.utils.util import current_local_time
from sqlalchemy import select

from utils.enums import StatementNotificationAction
from utils.mailer import StatementNotificationInfo, publish_payment_notification


# IMPORTANT: Due to the nature of dates, run this job at least 08:00 UTC or greater.
# Otherwise it could be triggered the day before due to timeshift for PDT/PST.
# It also needs to run after the statements job.
class EFTStatementDueTask:  # pylint: disable=too-few-public-methods
    """Task to notify admin for unpaid statements.

    This is currently for EFT payment method invoices only. This may be expanded to
    PAD and ONLINE BANKING in the future.
    """

    unpaid_status = [
        InvoiceStatus.SETTLEMENT_SCHEDULED.value,
        InvoiceStatus.PARTIAL.value,
        InvoiceStatus.APPROVED.value,
    ]
    action_date_override = None
    auth_account_override = None
    statement_date_override = None

    @classmethod
    def process_override_command(cls, action, date_override):
        """Process override action."""
        if date_override is None:
            current_app.logger.error(f"Expecting date override for action: {action}.")

        date_override = datetime.strptime(date_override, "%Y-%m-%d")
        match action:
            case "NOTIFICATION":
                cls.action_date_override = date_override.date()
                cls.statement_date_override = date_override
                cls._notify_for_monthly()
            case "OVERDUE":
                cls.action_date_override = date_override
                cls._update_invoice_overdue_status()
            case _:
                current_app.logger.error(f"Unsupported action override: {action}.")

    @classmethod
    def process_unpaid_statements(
        cls,
        action_override=None,
        date_override=None,
        auth_account_override=None,
        statement_date_override=None,
    ):
        """Notify for unpaid statements with an amount owing."""
        cls.auth_account_override = auth_account_override
        cls.statement_date_override = statement_date_override

        if action_override is not None and len(action_override.strip()) > 0:
            cls.process_override_command(action_override, date_override)
        else:
            cls._update_invoice_overdue_status()
            cls._notify_for_monthly()

    @classmethod
    def _update_invoice_overdue_status(cls):
        """Update the status of any invoices that are overdue."""
        # Needs to be non timezone aware.
        if cls.action_date_override:
            now = cls.action_date_override.replace(hour=8)
            offset_hours = -now.astimezone(pytz.timezone("America/Vancouver")).utcoffset().total_seconds() / 60 / 60
            now = now.replace(hour=int(offset_hours), minute=0, second=0)
        else:
            now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        query = db.session.query(InvoiceModel).filter(
            InvoiceModel.payment_method_code == PaymentMethod.EFT.value,
            InvoiceModel.overdue_date.isnot(None),
            InvoiceModel.overdue_date <= now,
            InvoiceModel.invoice_status_code.in_(cls.unpaid_status),
        )
        if cls.auth_account_override:
            current_app.logger.info(f"Using auth account override for auth_account_id: {cls.auth_account_override}")
            payment_account_id = (
                db.session.query(PaymentAccountModel.id)
                .filter(PaymentAccountModel.auth_account_id == cls.auth_account_override)
                .one()
            )
            query = query.filter(InvoiceModel.payment_account_id == payment_account_id[0])
        query.update(
            {InvoiceModel.invoice_status_code: InvoiceStatus.OVERDUE.value},
            synchronize_session="fetch",
        )
        db.session.commit()

        # Check for overdue accounts and lock them
        overdue_query = (
            select(PaymentAccountModel, StatementModel)
            .select_from(InvoiceModel)
            .join(PaymentAccountModel, PaymentAccountModel.id == InvoiceModel.payment_account_id)
            .join(StatementInvoicesModel, StatementInvoicesModel.invoice_id == InvoiceModel.id)
            .join(StatementModel, StatementModel.id == StatementInvoicesModel.statement_id)
            .filter(
                InvoiceModel.payment_method_code == PaymentMethod.EFT.value,
                InvoiceModel.invoice_status_code == InvoiceStatus.OVERDUE.value,
                InvoiceModel.overdue_date <= now,
                StatementModel.overdue_notification_date.is_(None),
            )
            .group_by(PaymentAccountModel.id, StatementModel.id)
        )
        if cls.auth_account_override:
            overdue_query = overdue_query.filter(PaymentAccountModel.auth_account_id == cls.auth_account_override)

        overdue_results = db.session.execute(overdue_query)
        accounts_to_lock = {}
        overdue_statement_ids = {}
        # Update statement overdue_notification_date and collect accounts so we don't lock it multiple times
        for payment_account, overdue_statement in overdue_results:
            accounts_to_lock[payment_account.id] = payment_account
            overdue_statement.overdue_notification_date = datetime.now(tz=timezone.utc)
            overdue_statement.save()
            overdue_statement_ids.setdefault(payment_account.id, [])
            overdue_statement_ids[payment_account.id].append(overdue_statement.id)

        for _, payment_account in accounts_to_lock.items():
            current_app.logger.info(
                "Freezing payment account id: %s locking auth account id: %s",
                payment_account.id,
                payment_account.auth_account_id,
            )

            # Only publish lock event if it is not already locked
            if payment_account.has_overdue_invoices is None:
                AuthEvent.publish_lock_account_event(
                    LockAccountDetails(
                        account_id=payment_account.auth_account_id,
                        additional_emails=current_app.config.get("EFT_OVERDUE_NOTIFY_EMAILS"),
                        payment_method=PaymentMethod.EFT.value,
                        source=QueueSources.PAY_JOBS.value,
                        suspension_reason_code=SuspensionReasonCodes.OVERDUE_EFT.value,
                        reversal_reason=",".join(overdue_statement_ids[payment_account.id])
                    )
                )

            # Even if the account is locked, there is a new overdue statement that needs NSF invoices added and
            # set the most recent date for has_overdue_invoices
            payment_account.has_overdue_invoices = datetime.now(tz=timezone.utc)
            payment_account.save()
            cls.add_to_non_sufficient_funds(payment_account)

    @classmethod
    def add_to_non_sufficient_funds(cls, payment_account):
        """Add the invoice to the non sufficient funds table."""
        invoices = (
            db.session.query(InvoiceModel.id, InvoiceReferenceModel.invoice_number)
            .join(
                InvoiceReferenceModel,
                InvoiceReferenceModel.invoice_id == InvoiceModel.id,
            )
            .filter(
                InvoiceModel.payment_account_id == payment_account.id,
                InvoiceModel.invoice_status_code == InvoiceStatus.OVERDUE.value,
                InvoiceModel.id.notin_(db.session.query(NonSufficientFundsModel.invoice_id)),
            )
            .distinct()
            .all()
        )
        cfs_account = CfsAccountModel.find_effective_by_payment_method(payment_account.id, PaymentMethod.EFT.value)
        for invoice_tuple in invoices:
            NonSufficientFundsService.save_non_sufficient_funds(
                invoice_id=invoice_tuple[0],
                invoice_number=invoice_tuple[1],
                cfs_account=cfs_account.cfs_account,
                description="EFT invoice overdue",
            )

    @classmethod
    def _notify_for_monthly(cls):
        """Notify for unpaid monthly statements with an amount owing."""
        previous_month = cls.statement_date_override or current_local_time().replace(day=1) - timedelta(days=1)
        statement_settings = StatementSettingsService.find_accounts_settings_by_frequency(
            previous_month, StatementFrequency.MONTHLY
        )
        eft_payment_accounts = [
            pay_account
            for _, pay_account in statement_settings
            if pay_account.payment_method == PaymentMethod.EFT.value
        ]
        if cls.auth_account_override:
            current_app.logger.info(f"Using auth account override for auth_account_id: {cls.auth_account_override}")
            eft_payment_accounts = [
                pay_account
                for pay_account in eft_payment_accounts
                if pay_account.auth_account_id == cls.auth_account_override
            ]

        current_app.logger.info(f"Processing {len(eft_payment_accounts)} EFT accounts for monthly reminders.")
        for payment_account in eft_payment_accounts:
            try:
                if not (
                    statement := cls._find_most_recent_statement(
                        payment_account.auth_account_id,
                        StatementFrequency.MONTHLY.value,
                    )
                ):
                    continue
                action, due_date = cls._determine_action_and_due_date_by_invoice(statement)
                total_due = Statement.get_summary(payment_account.auth_account_id, statement.id)["total_due"]
                if action and total_due > 0:
                    if emails := cls._determine_recipient_emails(statement):
                        current_app.logger.info(
                            f"Sending statement {statement.id} {action}"
                            f" notification for auth_account_id="
                            f"{payment_account.auth_account_id}, payment_account_id="
                            f"{payment_account.id}"
                        )
                        links_count = EFTShortnameLinksModel.get_short_name_links_count(payment_account.auth_account_id)
                        publish_payment_notification(
                            StatementNotificationInfo(
                                auth_account_id=payment_account.auth_account_id,
                                statement=statement,
                                action=action,
                                due_date=due_date,
                                emails=emails,
                                total_amount_owing=total_due,
                                short_name_links_count=links_count,
                            )
                        )
            except Exception:  # NOQA # pylint: disable=broad-except
                current_app.logger.error(
                    f"Error on unpaid statement notification auth_account_id={payment_account.auth_account_id}",
                    exc_info=True,
                )
                continue

    @classmethod
    def _find_most_recent_statement(cls, auth_account_id: str, statement_frequency: str) -> StatementModel:
        """Find all payment and invoices specific to a statement."""
        query = (
            db.session.query(StatementModel)
            .join(PaymentAccountModel)
            .filter(PaymentAccountModel.auth_account_id == auth_account_id)
            .filter(StatementModel.frequency == statement_frequency)
            .order_by(StatementModel.to_date.desc())
        )

        statement = query.first()
        return statement if statement and statement.overdue_notification_date is None else None

    @classmethod
    def _determine_action_and_due_date_by_invoice(cls, statement: StatementModel):
        """Find the most overdue invoice for a statement and provide an action."""
        invoice = (
            db.session.query(InvoiceModel)
            .join(
                StatementInvoicesModel,
                StatementInvoicesModel.invoice_id == InvoiceModel.id,
            )
            .filter(StatementInvoicesModel.statement_id == statement.id)
            .filter(InvoiceModel.overdue_date.isnot(None))
            .order_by(InvoiceModel.overdue_date.asc())
            .first()
        )

        if invoice is None:
            return None, None

        # 1. EFT Invoice created between or on January 1st <-> January 31st
        # 2. Statement Day February 1st
        # 3. 7 day reminder Feb 21th (due date - 7)
        # 4. Final reminder Feb 28th (due date client should be told to pay by this time)
        # 5. Overdue Date and account locked March 15th
        day_invoice_due = cls._get_last_day_of_next_month(statement.to_date)
        seven_days_before_invoice_due = day_invoice_due - timedelta(days=7)

        # Needs to be non timezone aware for comparison.
        if cls.action_date_override:
            now_date = cls.action_date_override
        else:
            now_date = datetime.now(tz=timezone.utc).replace(tzinfo=None).date()

        if day_invoice_due == now_date:
            return StatementNotificationAction.DUE, day_invoice_due
        if seven_days_before_invoice_due == now_date:
            return StatementNotificationAction.REMINDER, day_invoice_due
        return None, day_invoice_due

    @classmethod
    def _determine_recipient_emails(cls, statement: StatementRecipientsModel) -> str:
        if recipients := StatementRecipientsModel.find_all_recipients_for_payment_id(statement.payment_account_id):
            recipients = ",".join([str(recipient.email) for recipient in recipients])
            return recipients

        current_app.logger.error(f"No recipients found for payment_account_id: {statement.payment_account_id}. Skip.")
        return None

    @classmethod
    def _get_last_day_of_next_month(cls, date):
        """Find the last day of the next month."""
        next_month = date.replace(day=1) + timedelta(days=32)
        return next_month.replace(day=monthrange(next_month.year, next_month.month)[1])
