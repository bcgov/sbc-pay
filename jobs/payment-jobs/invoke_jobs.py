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
from tasks.routing_slip_task import RoutingSlipTask
from utils.logger import setup_logging


setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logging.conf'))  # important to do this first


def create_app(run_mode=os.getenv('FLASK_ENV', 'production')):
    """Return a configured Flask App using the Factory method."""
    from pay_api.models import db, ma

    app = Flask(__name__)

    app.config.from_object(config.CONFIGURATION[run_mode])
    # Configure Sentry
    if app.config.get('SENTRY_DSN', None):  # pragma: no cover
        sentry_sdk.init(
            dsn=app.config.get('SENTRY_DSN'),
            integrations=[FlaskIntegration()]
        )
    app.logger.info(f'<<<< Starting Payment Jobs >>>>')
    db.init_app(app)
    ma.init_app(app)

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


def run(job_name):
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
    from tasks.ap_routing_slip_refund_task import ApRoutingSlipRefundTask

    application = create_app()

    application.app_context().push()
    if job_name == 'UPDATE_GL_CODE':
        DistributionTask.update_failed_distributions()
        application.logger.info(f'<<<< Completed Updating GL Codes >>>>')
    elif job_name == 'GENERATE_STATEMENTS':
        StatementTask.generate_statements()
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
    elif job_name == 'ROUTING_SLIP':
        RoutingSlipTask.link_routing_slips()
        RoutingSlipTask.process_nsf()
        RoutingSlipTask.adjust_routing_slips()
        application.logger.info(f'<<<< Completed Routing Slip tasks >>>>')
    elif job_name == 'EJV_PAYMENT':
        EjvPaymentTask.create_ejv_file()
        application.logger.info(f'<<<< Completed running EJV payment >>>>')
    elif job_name == 'AP_REFUND':
        ApRoutingSlipRefundTask.create_ap_file()
        application.logger.info(f'<<<< Completed running AP Job for refund >>>>')
    else:
        application.logger.debug('No valid args passed.Exiting job without running any ***************')


if __name__ == "__main__":
    print('----------------------------Scheduler Ran With Argument--', sys.argv[1])
    run(sys.argv[1])
