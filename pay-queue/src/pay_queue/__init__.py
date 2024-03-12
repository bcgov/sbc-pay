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
"""The Reconciliations queue service.

This module is the service worker for applying payments, receipts and account balance to payment system.
"""
from __future__ import annotations

import os
import sentry_sdk
from flask import Flask
from sentry_sdk.integrations.flask import FlaskIntegration

from pay_api.models import db
from pay_api.services.flags import flags
from pay_queue.config import _Config, ProdConfig
from pay_queue.version import __version__

from .resources import register_endpoints
from .services import queue


def get_run_version():
    """Get the git commit hash if available."""
    commit_hash = os.getenv('OPENSHIFT_BUILD_COMMIT', None)
    if commit_hash:
        return f'{__version__}-{commit_hash}'
    return __version__


def create_app(environment: _Config = ProdConfig) -> Flask:
    """Return a configured Flask App using the Factory method."""
    app = Flask(__name__)
    app.config.from_object(environment)

    # Configure Sentry
    if dsn := app.config.get('SENTRY_DSN', None):
        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            release=f'pay-queue@{get_run_version()}',
            send_default_pii=False,
        )

    flags.init_app(app)
    db.init_app(app)
    queue.init_app(app)

    register_endpoints(app)

    return app
