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

import sentry_sdk
from flask import Flask
from flask_restx import Api
from namex.models import db
from namex.resources.ops import api as nr_ops
from sentry_sdk.integrations.flask import FlaskIntegration

from config import Config, ProdConfig
from reconciliation.utils import get_run_version

from .resources import register_endpoints
from .services import queue



def _get_build_openshift_commit_hash():
    return os.getenv('OPENSHIFT_BUILD_COMMIT', None)

def get_run_version():
    commit_hash = _get_build_openshift_commit_hash()
    if commit_hash:
        return f'{__version__}-{commit_hash}'
    return __version__

def create_app(environment: Config = ProdConfig) -> Flask:
    """Return a configured Flask App using the Factory method."""
    # APP_CONFIG = config.get_named_config(os.getenv('DEPLOYMENT_ENV', 'production'))
    app = Flask(__name__)
    app.config.from_object(environment)

    # Configure Sentry
    if dsn := app.config.get("SENTRY_DSN", None):
        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            release=f"payment-reconciliation@{get_run_version()}",
            send_default_pii=False,
        )

    db.init_app(app)
    queue.init_app(app)
    flag_service = Flags(FLASK_APP)

    register_endpoints(app)

    api = Api()

    api.add_namespace(nr_ops, path='/ops')  # TODO Fix
    api.init_app(app)

    return app
