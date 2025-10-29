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
    app.secret_key = os.getenv("SECRET_KEY", "test_key")

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

    @app.route('/debug/flask-oidc-session')
    def debug_flask_oidc_session():
        """Inspect Flask session and cookies for OIDC debugging."""
        from flask import current_app, request, session
        cookie_name = current_app.config.get("SESSION_COOKIE_NAME", "session")
        cookie_value = request.cookies.get(cookie_name)

        debug_info = {
            "session_keys": list(session.keys()),
            "has__oidc_auth_state": "_oidc_auth_state" in session,
            "has_oidc_state": "oidc_state" in session,
            "session_cookie_name": cookie_name,
            "session_cookie_present": cookie_value is not None,
            "session_cookie_value_snippet": cookie_value[:30] + "..." if cookie_value else None,
            "session_cookie_secure": current_app.config.get("SESSION_COOKIE_SECURE"),
            "session_cookie_samesite": current_app.config.get("SESSION_COOKIE_SAMESITE"),
        }

        print("DEBUG /debug/flask-oidc-session:", debug_info)
        return debug_info

    @app.route('/debug/oauth-callback')
    def debug_oauth_callback():
        from flask import current_app, request, session
        state_from_url = request.args.get('state')
        state_from_session = session.get('oidc_state')

        cookie_name = current_app.config.get("SESSION_COOKIE_NAME", "session")
        cookie_value = request.cookies.get(cookie_name)

        debug_info = {
            "url_state": state_from_url,
            "session_state": state_from_session,
            "state_match": state_from_url == state_from_session,
            "cookie_name": cookie_name,
            "cookie_present": cookie_value is not None,
            "cookie_value_snippet": cookie_value[:30] + "..." if cookie_value else None,
            "session_keys": list(session.keys()),
            "remote_addr": request.remote_addr,
            "headers": dict(request.headers),
        }

        print("DEBUG /debug/oauth-callback:", debug_info)

        if debug_info["state_match"]:
            return {"result": "SUCCESS", **debug_info}
        else:
            return {"result": "FAIL", **debug_info}, 400

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
