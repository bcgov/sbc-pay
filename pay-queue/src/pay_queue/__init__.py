# Copyright © 2024 Province of British Columbia
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
"""The pay-queue service.

The service worker for applying payments, receipts and account balance to payment system.
"""
from __future__ import annotations

import os

import sentry_sdk
from flask import Flask
from pay_api.models import db
from pay_api.services.flags import flags
from pay_api.utils.logging import setup_logging
from pay_api.utils.run_version import get_run_version
from sentry_sdk.integrations.flask import FlaskIntegration

from pay_queue import config
from pay_queue.version import __version__

from .resources import register_endpoints
from .services import queue


setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logging.conf'))  # important to do this first


def create_app(run_mode=os.getenv('DEPLOYMENT_ENV', 'production')) -> Flask:
    """Return a configured Flask App using the Factory method."""
    app = Flask(__name__)
    app.env = run_mode
    app.config.from_object(config.CONFIGURATION[run_mode])

    # Configure Sentry
    if dsn := app.config.get('SENTRY_DSN', None):
        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            release=f'pay-queue@{get_run_version()}',
            send_default_pii=False,
        )

    queue.init_app(app)
    flags.init_app(app)
    db.init_app(app)

    register_endpoints(app)

    return app
