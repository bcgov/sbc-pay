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

setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logging.conf'))  # important to do this first

# lower case name as used by convention in most Flask apps
jwt = JwtManager()  # pylint: disable=invalid-name


def create_app(run_mode=os.getenv('FLASK_ENV', 'production')):
    """Return a configured Flask App using the Factory method."""
    app = Flask(__name__)

    app.config.from_object(config.CONFIGURATION[run_mode])
    app.logger.info(f'Rectify GL CODE Job Ran-----------------------------------------------!')
    db.init_app(app)
    ma.init_app(app)

    setup_jwt_manager(app, jwt)

    register_shellcontext(app)

    return app


def setup_jwt_manager(app, jwt_manager):
    """Use flask app to configure the JWTManager to work for a particular Realm."""

    def get_roles(a_dict):
        return a_dict['realm_access']['roles']  # pragma: no cover

    app.config['JWT_ROLE_CALLBACK'] = get_roles

    jwt_manager.init_app(app)


def register_shellcontext(app):
    """Register shell context objects."""

    def shell_context():
        """Shell context objects."""
        return {
            'app': app,
            'jwt': jwt}  # pragma: no cover

    app.shell_context_processor(shell_context)


def run():
    application = create_app()
    application.logger.debug('Ran Batch Job--*************************************************************')

    application.app_context().push()
    find_failed_distr(application)


def find_failed_distr(app):
    """Update stale payment records. 
    
    This is to handle edge cases where the user has completed payment and some error occured and payment status is not up-to-date.
    """
    stale_transactions = PaymentTransactionModel.find_stale_records(hours=4)
    if len(stale_transactions) == 0:
        app.logger.info(f'Stale Transaction Job Ran at {datetime.datetime.now()}.But No records found!')


if __name__ == "__main__":
    run()
