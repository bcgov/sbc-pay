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
import time

from flask import Flask

import config
from pay_api import build_cache
from pay_api.services import Flags
from pay_api.services.email_service import JobFailureNotification
from pay_api.services.gcp_queue import queue
from pay_api.utils.logging import setup_logging
from services import data_warehouse
from tasks.eft_overpayment_notification_task import EFTOverpaymentNotificationTask
from tasks.eft_statement_due_task import EFTStatementDueTask
from tasks.eft_task import EFTTask
from tasks.permission_check import PayJobPermissionCheckTask
from tasks.routing_slip_task import RoutingSlipTask

setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), "logging.conf"))  # important to do this first


def create_app(
    run_mode=None,
    init_data_warehouse=False,
):
    """Return a configured Flask App using the Factory method."""
    from pay_api.models import db, ma

    if run_mode is None:
        run_mode = os.getenv("DEPLOYMENT_ENV", "production")

    app = Flask(__name__)
    app.env = run_mode

    app.config.from_object(config.CONFIGURATION[run_mode])

    # If Cloud SQL connection info is present, configure SQLAlchemy engine options
    if app.config.get("CLOUDSQL_INSTANCE_CONNECTION_NAME"):
        try:
            from cloud_sql_connector import DBConfig

            db_config = DBConfig(
                instance_name=app.config.get("CLOUDSQL_INSTANCE_CONNECTION_NAME"),
                database=app.config.get("DB_NAME", ""),
                user=app.config.get("DB_USER", ""),
                ip_type=app.config.get("DB_IP_TYPE"),
                schema="public",
                pool_timeout=30,
                max_overflow=3,
            )

            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = db_config.get_engine_options()
        except Exception:
            app.logger.exception("Failed to configure Cloud SQL DBConfig")
            raise

    app.logger.info("<<<< Starting Payment Jobs >>>>")
    queue.init_app(app)
    db.init_app(app)
    if init_data_warehouse:
        data_warehouse.init_app(app)

    ma.init_app(app)
    flag_service = Flags()
    flag_service.init_app(app)

    register_shellcontext(app)
    build_cache(app)

    return app


def register_shellcontext(app):
    """Register shell context objects."""

    def shell_context():
        """Shell context objects."""
        return {"app": app}  # pragma: no cover

    app.shell_context_processor(shell_context)


def run(job_name, argument=None):
    """Run the specified job with optional arguments."""
    from tasks.activate_pad_account_task import ActivatePadAccountTask
    from tasks.adhoc.invoice_status_check import AdhocInvoiceStatusCheckTask
    from tasks.ap_task import ApTask
    from tasks.bcol_refund_confirmation_task import BcolRefundConfirmationTask
    from tasks.cfs_create_account_task import CreateAccountTask
    from tasks.cfs_create_invoice_task import CreateInvoiceTask
    from tasks.direct_sale_automated_refund_task import DirectSaleAutomatedRefundTask
    from tasks.distribution_task import DistributionTask
    from tasks.ejv_partner_distribution_task import EjvPartnerDistributionTask
    from tasks.ejv_payment_task import EjvPaymentTask
    from tasks.stale_payment_task import StalePaymentTask
    from tasks.statement_notification_task import StatementNotificationTask
    from tasks.statement_task import StatementTask
    from tasks.unpaid_invoice_notify_task import UnpaidInvoiceNotifyTask

    jobs_with_data_warehouse_connections = ["BCOL_REFUND_CONFIRMATION"]

    application = create_app(init_data_warehouse=job_name in jobs_with_data_warehouse_connections)
    application.app_context().push()

    application.logger.info(f"job_name={job_name} status=started")
    start = time.monotonic()
    try:
        match job_name:
            case "UPDATE_GL_CODE":
                DistributionTask.update_failed_distributions()
            case "GENERATE_STATEMENTS":
                StatementTask.generate_statements(argument)
            case "SEND_NOTIFICATIONS":
                StatementNotificationTask.send_notifications()
            case "UPDATE_STALE_PAYMENTS":
                StalePaymentTask.update_stale_payments()
            case "UPDATE_STALE_PAYMENTS_DAILY":
                StalePaymentTask.update_stale_payments(daily_run=True)
            case "CREATE_CFS_ACCOUNTS":
                CreateAccountTask.create_accounts()
            case "CREATE_INVOICES":
                CreateInvoiceTask.create_invoices()
            case "ACTIVATE_PAD_ACCOUNTS":
                ActivatePadAccountTask.activate_pad_accounts()
            case "EJV_PARTNER":
                EjvPartnerDistributionTask.create_ejv_file()
            case "NOTIFY_UNPAID_INVOICE_OB":
                UnpaidInvoiceNotifyTask.notify_unpaid_invoices()
            case "STATEMENTS_DUE":
                action_override = argument[0] if argument and len(argument) >= 1 else None
                date_override = argument[1] if argument and len(argument) >= 2 else None
                auth_account_override = argument[2] if argument and len(argument) >= 3 else None
                application.logger.info(
                    f"job_name={job_name} action={action_override} date={date_override} account={auth_account_override}"
                )
                EFTStatementDueTask.process_unpaid_statements(
                    action_override=action_override,
                    date_override=date_override,
                    auth_account_override=auth_account_override,
                )
            case "ROUTING_SLIP":
                RoutingSlipTask.link_routing_slips()
                RoutingSlipTask.process_void()
                RoutingSlipTask.process_nsf()
                RoutingSlipTask.process_correction()
                RoutingSlipTask.adjust_routing_slips()
            case "EFT":
                EFTTask.link_electronic_funds_transfers_cfs()
                EFTTask.reverse_electronic_funds_transfers_cfs()
            case "EFT_OVERPAYMENT":
                date_override = argument[0] if argument and len(argument) >= 1 else None
                EFTOverpaymentNotificationTask.process_overpayment_notification(date_override=date_override)
            case "EJV_PAYMENT":
                EjvPaymentTask.create_ejv_file()
            case "AP":
                ApTask.create_ap_files()
            case "DIRECT_PAY_REFUND":
                DirectSaleAutomatedRefundTask.process_cc_refunds()
            case "BCOL_REFUND_CONFIRMATION":
                BcolRefundConfirmationTask.update_bcol_refund_invoices()
            case "ADHOC_INVOICE_STATUS_CHECK":
                AdhocInvoiceStatusCheckTask.check_invoice_statuses()
            case "PERMISSION_CHECK":
                PayJobPermissionCheckTask.check()
            case _:
                application.logger.warning(f"job_name={job_name} status=unknown_job")
                return

        duration_ms = int((time.monotonic() - start) * 1000)
        application.logger.info(f"job_name={job_name} status=completed duration_ms={duration_ms}")
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        application.logger.error(f"job_name={job_name} status=failed duration_ms={duration_ms} error={e}")
        send_notification(str(e), job_name)
        raise


def send_notification(error_message: str, job_name: str):
    """Send notification for job failure."""
    notification = JobFailureNotification(
        subject=f"Invoke Job Failure - {job_name}",
        file_name="ejv_partner_distribution",
        error_messages=[{"error": error_message}],
        table_name=None,
        job_name=job_name,
    )
    notification.send_notification()


if __name__ == "__main__":
    print("----------------------------Scheduler Ran With Argument--", sys.argv[1])  # noqa: T201
    if len(sys.argv) > 2:
        params = sys.argv[2 : len(sys.argv)]
        run(sys.argv[1], params)
    else:
        run(sys.argv[1])
