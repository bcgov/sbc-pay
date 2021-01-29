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
from datetime import datetime, timedelta

from flask import current_app
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.utils.enums import InvoiceStatus, PaymentMethod
from sentry_sdk import capture_message
from sqlalchemy import Date, and_, cast

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
        """Notify for online banking."""
        unpaid_status = (
            InvoiceStatus.SETTLEMENT_SCHEDULED.value, InvoiceStatus.PARTIAL.value, InvoiceStatus.CREATED.value)
        notification_date = datetime.today() - timedelta(days=current_app.config.get('NOTIFY_AFTER_DAYS'))
        notification_pending_invoices = InvoiceModel.query.filter(and_(
            InvoiceModel.invoice_status_code.in_(unpaid_status),
            InvoiceModel.payment_method_code == PaymentMethod.ONLINE_BANKING.value,
            # cast is used to get the exact match stripping the timestamp from date
            cast(InvoiceModel.created_on, Date) == notification_date.date()
        )).all()
        current_app.logger.debug(f'Found {len(notification_pending_invoices)} invoices to notify admins.')
        for invoice in notification_pending_invoices:
            # Find all PAD invoices for this account
            try:
                pay_account: PaymentAccountModel = PaymentAccountModel.find_by_id(invoice.payment_account_id)
                cfs_account = CfsAccountModel.find_by_id(invoice.cfs_account_id)

                # emit account mailer event
                addition_params_to_mailer = {'transactionAmount': invoice.total,
                                             'cfsAccountId': cfs_account.cfs_account}
                mailer.publish_mailer_events('ob.invoicePending', pay_account, addition_params_to_mailer)

            except Exception as e:  # NOQA # pylint: disable=broad-except
                capture_message(f'Error on notifying mailer  OB Pending invoice: account id={pay_account.id}, '
                                f'auth account : {pay_account.auth_account_id}, ERROR : {str(e)}', level='error')
                current_app.logger.error(e)
