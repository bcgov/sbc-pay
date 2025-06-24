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
"""Task to notify user for any outstanding invoice for online banking."""
from datetime import datetime, timedelta, timezone

from flask import current_app
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import db
from pay_api.utils.enums import InvoiceStatus, PaymentMethod
from sbc_common_components.utils.enums import QueueMessageTypes
from sqlalchemy import Date, and_, cast, func

from utils import mailer


class UnpaidInvoiceNotifyTask:  # pylint:disable=too-few-public-methods
    """Task to notify admin for unpaid invoices."""

    @classmethod
    def notify_unpaid_invoices(cls):
        """Create invoice in CFS.

        Steps:
        1. Find all pending invoices from invoice table for Online Banking.
        1. Notify mailer
        """
        cls._notify_for_ob()

    @classmethod
    def _notify_for_ob(cls):  # pylint: disable=too-many-locals
        """Notify for online banking.

        1) Find the accounts with pending invoices
        2) get total remaining for that account

        """
        unpaid_status = (
            InvoiceStatus.SETTLEMENT_SCHEDULED.value,
            InvoiceStatus.PARTIAL.value,
            InvoiceStatus.CREATED.value,
        )
        notification_date = datetime.now(tz=timezone.utc) - timedelta(days=current_app.config.get("NOTIFY_AFTER_DAYS"))
        # Get distinct accounts with pending invoices for that exact day
        notification_pending_accounts = (
            db.session.query(InvoiceModel.payment_account_id)
            .distinct()
            .filter(
                and_(
                    InvoiceModel.invoice_status_code.in_(unpaid_status),
                    InvoiceModel.payment_method_code == PaymentMethod.ONLINE_BANKING.value,
                    # cast is used to get the exact match stripping the timestamp from date
                    cast(InvoiceModel.created_on, Date) == notification_date.date(),
                )
            )
            .all()
        )
        current_app.logger.debug(f"Found {len(notification_pending_accounts)} invoices to notify admins.")
        for payment_account in notification_pending_accounts:
            try:
                payment_account_id = payment_account[0]
                total = (
                    db.session.query(func.sum(InvoiceModel.total).label("total"))
                    .filter(
                        and_(
                            InvoiceModel.invoice_status_code.in_(unpaid_status),
                            InvoiceModel.payment_account_id == payment_account_id,
                            InvoiceModel.payment_method_code == PaymentMethod.ONLINE_BANKING.value,
                        )
                    )
                    .group_by(InvoiceModel.payment_account_id)
                    .all()
                )
                pay_account: PaymentAccountModel = PaymentAccountModel.find_by_id(payment_account_id)

                cfs_account = CfsAccountModel.find_effective_by_payment_method(
                    payment_account_id, PaymentMethod.ONLINE_BANKING.value
                )

                # emit account mailer event
                addition_params_to_mailer = {
                    "transactionAmount": float(total[0][0]),
                    "cfsAccountId": cfs_account.cfs_account,
                    "authAccountId": pay_account.auth_account_id,
                }
                mailer.publish_mailer_events(
                    QueueMessageTypes.PAYMENT_PENDING.value,
                    pay_account,
                    addition_params_to_mailer,
                )
            except Exception as e:  # NOQA # pylint: disable=broad-except
                current_app.logger.error(
                    f"Error on notifying mailer  OB Pending invoice: account id={pay_account.id}, "
                    f"auth account : {pay_account.auth_account_id}, ERROR : {str(e)}",
                    exc_info=True
                )
