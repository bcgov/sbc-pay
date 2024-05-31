# Copyright © 2019 Province of British Columbia
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
"""Generate account statements.

This module will create statement records for each account.
"""
import os
import sys

import sentry_sdk
from flask import Flask
from sentry_sdk.integrations.flask import FlaskIntegration

import config
from services import oracle_db
from tasks.routing_slip_task import RoutingSlipTask
from tasks.electronic_funds_transfer_task import ElectronicFundsTransferTask
from tasks.statement_due_task import StatementDueTask
from utils.logger import setup_logging

from pay_api.services import Flags
from pay_api.services.gcp_queue import queue

setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logging.conf'))  # important to do this first


def create_app(run_mode=os.getenv('DEPLOYMENT_ENV', 'production'), job_name='unknown', init_oracle=False):
    """Return a configured Flask App using the Factory method."""
    from pay_api.models import db, ma

    app = Flask(__name__)
    app.env = run_mode

    app.config.from_object(config.CONFIGURATION[run_mode])
    # Configure Sentry
    if str(app.config.get('SENTRY_ENABLE')).lower() == 'true':
        if app.config.get('SENTRY_DSN', None):
            sentry_sdk.init(
                dsn=app.config.get('SENTRY_DSN'),
                integrations=[FlaskIntegration()],
                release=f'payment-jobs-{job_name}@-',
            )
    app.logger.info('<<<< Starting Payment Jobs >>>>')
    queue.init_app(app)
    db.init_app(app)
    if init_oracle:
        oracle_db.init_app(app)
    ma.init_app(app)
    flag_service = Flags()
    flag_service.init_app(app)

    register_shellcontext(app)

    return app


def register_shellcontext(app):
    """Register shell context objects."""

    def shell_context():
        """Shell context objects."""
        return {
            'app': app
        }  # pragma: no cover

    app.shell_context_processor(shell_context)


def run(job_name, argument=None):
    from tasks.cfs_create_account_task import CreateAccountTask
    from tasks.cfs_create_invoice_task import CreateInvoiceTask
    from tasks.distribution_task import DistributionTask
    from tasks.stale_payment_task import StalePaymentTask
    from tasks.statement_notification_task import StatementNotificationTask
    from tasks.statement_task import StatementTask
    from tasks.activate_pad_account_task import ActivatePadAccountTask
    from tasks.ejv_partner_distribution_task import EjvPartnerDistributionTask
    from tasks.unpaid_invoice_notify_task import UnpaidInvoiceNotifyTask
    from tasks.ejv_payment_task import EjvPaymentTask
    from tasks.ap_task import ApTask
    from tasks.direct_pay_automated_refund_task import DirectPayAutomatedRefundTask
    from tasks.bcol_refund_confirmation_task import BcolRefundConfirmationTask

    jobs_with_oracle_connections = ['BCOL_REFUND_CONFIRMATION']
    application = create_app(job_name=job_name, init_oracle=job_name in jobs_with_oracle_connections)

    application.app_context().push()
    if job_name == 'UPDATE_GL_CODE':
        DistributionTask.update_failed_distributions()
        application.logger.info(f'<<<< Completed Updating GL Codes >>>>')
    elif job_name == 'GENERATE_STATEMENTS':
        StatementTask.generate_statements(argument)
        application.logger.info(f'<<<< Completed Generating Statements >>>>')
    elif job_name == 'SEND_NOTIFICATIONS':
        StatementNotificationTask.send_notifications()
        application.logger.info(f'<<<< Completed Sending notifications >>>>')
    elif job_name == 'UPDATE_STALE_PAYMENTS':
        StalePaymentTask.update_stale_payments()
        application.logger.info(f'<<<< Completed Updating stale payments >>>>')
    elif job_name == 'CREATE_CFS_ACCOUNTS':
        CreateAccountTask.create_accounts()
        application.logger.info(f'<<<< Completed creating cfs accounts >>>>')
    elif job_name == 'CREATE_INVOICES':
        CreateInvoiceTask.create_invoices()
        application.logger.info(f'<<<< Completed creating cfs invoices >>>>')
    elif job_name == 'ACTIVATE_PAD_ACCOUNTS':
        ActivatePadAccountTask.activate_pad_accounts()
        application.logger.info(f'<<<< Completed Activating PAD accounts >>>>')
    elif job_name == 'EJV_PARTNER':
        EjvPartnerDistributionTask.create_ejv_file()
        application.logger.info(f'<<<< Completed Creating EJV File for partner distribution>>>>')
    elif job_name == 'NOTIFY_UNPAID_INVOICE_OB':
        UnpaidInvoiceNotifyTask.notify_unpaid_invoices()
        application.logger.info(f'<<<< Completed Sending notification for OB invoices >>>>')
    elif job_name == 'STATEMENTS_DUE':
        StatementDueTask.process_unpaid_statements()
        application.logger.info(f'<<<< Completed Sending notification for unpaid statements >>>>')
    elif job_name == 'ROUTING_SLIP':
        RoutingSlipTask.link_routing_slips()
        RoutingSlipTask.process_void()
        RoutingSlipTask.process_nsf()
        RoutingSlipTask.process_correction()
        RoutingSlipTask.adjust_routing_slips()
        application.logger.info(f'<<<< Completed Routing Slip tasks >>>>')
    elif job_name == 'EFT':
        ElectronicFundsTransferTask.link_electronic_funds_transfers()
        ElectronicFundsTransferTask.unlink_electronic_funds_transfers()
        application.logger.info(f'<<<< Completed EFT tasks >>>>')
    elif job_name == 'EJV_PAYMENT':
        EjvPaymentTask.create_ejv_file()
        application.logger.info(f'<<<< Completed running EJV payment >>>>')
    elif job_name == 'AP':
        ApTask.create_ap_files()
        application.logger.info(f'<<<< Completed running AP Job for refund >>>>')
    elif job_name == 'DIRECT_PAY_REFUND':
        DirectPayAutomatedRefundTask.process_cc_refunds()
        application.logger.info(f'<<<< Completed running Direct Pay Automated Refund Job >>>>')
    elif job_name == 'BCOL_REFUND_CONFIRMATION':
        BcolRefundConfirmationTask.update_bcol_refund_invoices()
        application.logger.info(f'<<<< Completed running BCOL Refund Confirmation Job >>>>')
    else:
        application.logger.debug('No valid args passed. Exiting job without running any ***************')


if __name__ == "__main__":
    print('----------------------------Scheduler Ran With Argument--', sys.argv[1])
    if (len(sys.argv) > 2):
        run(sys.argv[1], sys.argv[2])
    else:
        run(sys.argv[1])
