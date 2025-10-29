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
"""The Payment API service.

This module is the API for the Legal Entity system.
"""

import os

from flask import Flask, redirect
from flask_admin import Admin
from flask_caching import Cache
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix

from admin import config
from admin.config import _Config
from admin.views import CodeConfig, CorpTypeView, DistributionCodeView, FeeCodeView, FeeScheduleView, IndexView
from pay_api.models import FilingType, db, ma
from pay_api.utils.logging import setup_logging

from .keycloak import Keycloak

setup_logging(os.path.join(_Config.PROJECT_ROOT, "logging.conf"))


def create_app(run_mode=None):
    """Return a configured Flask App using the Factory method."""
    if run_mode is None:
        run_mode = os.getenv("DEPLOYMENT_ENV", "production")

    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=0)
    app.config.from_object(config.CONFIGURATION[run_mode])

    app.secret_key = os.getenv("SECRET_KEY", os.urandom(24))

    app.logger.info("init db.")
    db.init_app(app)
    ma.init_app(app)

    app.logger.info("init flask admin.")
    init_flask_admin(app)

    app.logger.info("init cache.")
    Cache(app)

    app.logger.info("init session.")
    Session(app)

    app.logger.info("init keycloak.")
    Keycloak(app)

    @app.route("/")
    def index():
        return redirect("/admin/feecode/")

    app.logger.info("create_app is complete.")
    return app


def init_flask_admin(app):
    """Initialize flask admin and it's views."""
    flask_admin = Admin(app, name="Fee Admin", template_mode="bootstrap4", index_view=IndexView())
    flask_admin.add_view(FeeCodeView)
    flask_admin.add_view(CorpTypeView)
    flask_admin.add_view(CodeConfig(FilingType, db.session))
    flask_admin.add_view(FeeScheduleView)
    flask_admin.add_view(DistributionCodeView)
    return flask_admin
