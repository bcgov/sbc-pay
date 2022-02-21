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
from typing import List

import sentry_sdk
from flask import Flask
from flask import current_app
from pay_api.models import CfsAccount
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import db, ma
from pay_api.utils.enums import PaymentMethod
from sentry_sdk.integrations.flask import FlaskIntegration
from pay_api.services.cfs_service import CFSService

import config
from utils.logger import setup_logging

setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logging.conf'))  # important to do this first


def create_app(run_mode=os.getenv('FLASK_ENV', 'production')):
    """Return a configured Flask App using the Factory method."""

    app = Flask(__name__)

    app.config.from_object(config.CONFIGURATION[run_mode])
    # Configure Sentry
    if app.config.get('SENTRY_DSN', None):  # pragma: no cover
        sentry_sdk.init(
            dsn=app.config.get('SENTRY_DSN'),
            integrations=[FlaskIntegration()]
        )
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


def run_update(pay_account_id, num_records):
    current_app.logger.info(f'<<<< Running Update for account id from :{pay_account_id} and total:{num_records} >>>>')
    pad_accounts: List[PaymentAccountModel] = db.session.query(PaymentAccountModel).filter(
        PaymentAccountModel.payment_method == PaymentMethod.PAD.value) \
        .filter(PaymentAccountModel.id >= pay_account_id) \
        .limit(num_records) \
        .all()
    current_app.logger.info(f'<<<< Total number of records founds: {len(pad_accounts)}')
    for payment_account in pad_accounts:
        cfs_account: CfsAccount = CfsAccount.find_effective_by_account_id(payment_account.id)
        current_app.logger.info(
            f'<<<< Running Update for account id :{payment_account.id} and cfs_account:{cfs_account.id} and bank account: {cfs_account.bank_account_number} >>>>')

        payment_details = CFSService.get_bank_info(cfs_account.cfs_party, cfs_account.account_id,cfs_account.cfs_site)
        current_app.logger.info('<<<<<<<<<<<<<<<<<<<<<<')
        current_app.logger.info(payment_details)


def run(account_id, total_records):
    application = create_app()
    application.app_context().push()
    run_update(account_id, total_records)


if __name__ == "__main__":
    print('len:', len(sys.argv))
    if len(sys.argv) <= 2:
        print('No valid args passed.Exiting job without running any ***************')
    cnt = sys.argv[2] if len(sys.argv) == 3 else 10
    run(sys.argv[1], cnt)
