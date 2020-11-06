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
    app.logger.info(f'<<<< Starting Ftp Poller Job >>>>')
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
    from tasks.poll_ftp_task import PollFtpTask

    application = create_app()

    application.app_context().push()
    if job_name == 'FTP_POLLER':
        PollFtpTask.poll_ftp()
        application.logger.info(f'<<<< Completed Polling FTP >>>>')
    else:
        PollFtpTask.poll_ftp()
        application.logger.debug('No valid args passed.Exiting job without running any ***************')


if __name__ == "__main__":
    print('----------------------------Scheduler Ran With Argument--')
    run('FTP_POLLER')
