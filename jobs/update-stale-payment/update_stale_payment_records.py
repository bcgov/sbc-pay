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

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

from flask import Flask
from flask_jwt_oidc import JwtManager
from pay_api.exceptions import BusinessException
from pay_api.models import PaymentTransaction as PaymentTransactionModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import db, ma
from pay_api.services import TransactionService
from pay_api.services import PaymentService
from utils.logging import setup_logging

import config

setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logging.conf'))  # important to do this first

# lower case name as used by convention in most Flask apps
jwt = JwtManager()  # pylint: disable=invalid-name


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
    application.logger.debug('Ran Batch Job--')

    application.app_context().push()
    update_stale_payments(application)
    delete_marked_payments(application)


def update_stale_payments(app):
    """Update stale payment records. 
    
    This is to handle edge cases where the user has completed payment and some error occured and payment status is not up-to-date.
    """
    stale_transactions = PaymentTransactionModel.find_stale_records(minutes=30)
    if len(stale_transactions) == 0:
        app.logger.info(f'Stale Transaction Job Ran at {datetime.datetime.now()}.But No records found!')
    for transaction in stale_transactions:
        try:
            app.logger.info(
                'Stale Transaction Job found records.Payment Id: {}, Transaction Id : {}'.format(transaction.payment_id,
                                                                                                 transaction.id))
            TransactionService.update_transaction(transaction.payment_id, transaction.id, '')
            app.logger.info(
                'Stale Transaction Job Updated records.Payment Id: {}, Transaction Id : {}'.format(
                    transaction.payment_id, transaction.id))
        except BusinessException as err:  # just catch and continue .Don't stop
            app.logger.error('Stale Transaction Error on update_transaction')
            app.logger.error(err)


def delete_marked_payments(app):
    """Update stale payment records. 
    
    This is to handle edge cases where the user has completed payment and some error occured and payment status is not up-to-date.
    """
    payments_to_delete = PaymentModel.find_payments_marked_for_delete()
    if len(payments_to_delete) == 0:
        app.logger.info(f'Delete Payment Job Ran at {datetime.datetime.now()}.But No records found!')
    for payment in payments_to_delete:
        try:
            app.logger.info('Delete Payment Job found records.Payment Id: {}'.format(payment.id))
            PaymentService.delete_payment(payment.id)
            app.logger.info(
                'Delete Payment Job Updated records.Payment Id: {}'.format(payment.id))
        except BusinessException as err:  # just catch and continue .Don't stop
            app.logger.error('Error on delete_payment')
            app.logger.error(err)


if __name__ == "__main__":
    run()
