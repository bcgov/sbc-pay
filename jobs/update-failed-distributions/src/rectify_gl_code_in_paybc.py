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
"""The Update Payment Job.

This module is being invoked from a job and it cleans up the stale records
"""
import datetime
import os

import config
from flask import Flask
from flask_jwt_oidc import JwtManager
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.models import db, ma
from utils.logger import setup_logging
from services.distribution_service import DistributionService
setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logging.conf'))  # important to do this first


def create_app(run_mode=os.getenv('FLASK_ENV', 'production')):
    """Return a configured Flask App using the Factory method."""
    app = Flask(__name__)

    app.config.from_object(config.CONFIGURATION[run_mode])
    app.logger.info(f'Rectify GL CODE Job Ran-----------------------------------------------!')
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


def run():
    application = create_app()
    application.logger.debug('Ran Batch Job--*************************************************************')

    application.app_context().push()
    DistributionService.update_failed_distributions()


if __name__ == "__main__":
    run()
