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
"""The Payment API service.

This module is the API for the Payment system.
"""

import os

from flask import Flask, request
from flask_migrate import Migrate, upgrade
from sbc_common_components.exception_handling.exception_handler import ExceptionHandler
from sbc_common_components.utils.camel_case_response import convert_to_camel

from pay_api import config
from pay_api.config import _Config
from pay_api.models import db, ma
from pay_api.resources import endpoints
from pay_api.services.flags import flags
from pay_api.services.gcp_queue import queue
from pay_api.utils.auth import jwt
from pay_api.utils.cache import cache
from pay_api.utils.logging import setup_logging
from pay_api.utils.run_version import get_run_version
from pay_api.utils.user_context import _get_context

setup_logging(os.path.join(_Config.PROJECT_ROOT, "logging.conf"), _Config.LOGGING_OVERRIDE_CONFIG)


def create_app(run_mode=None):
    """Return a configured Flask App using the Factory method."""
    if run_mode is None:
        run_mode = os.getenv("DEPLOYMENT_ENV", "production")
    app = Flask(__name__)
    app.env = run_mode
    app.config.from_object(config.CONFIGURATION[run_mode])

    flags.init_app(app)
    db.init_app(app)
    queue.init_app(app)
    if run_mode != "testing":
        if app.config.get("CLOUD_PLATFORM") != "OCP":
            Migrate(app, db)
            app.logger.info(f"Booting up with CPU count (useful for GCP): {os.cpu_count()}")
            app.logger.info("Running migration upgrade.")
            with app.app_context():
                execute_migrations(app)
            # Alembic has it's own logging config, we'll need to restore our logging here.
            setup_logging(os.path.join(_Config.PROJECT_ROOT, "logging.conf"), _Config.LOGGING_OVERRIDE_CONFIG)
            app.logger.info("Finished migration upgrade.")
        else:
            app.logger.info("Migrations were executed on prehook.")
    ma.init_app(app)
    endpoints.init_app(app)

    app.after_request(convert_to_camel)

    setup_jwt_manager(app, jwt)
    ExceptionHandler(app)
    setup_403_logging(app)

    @app.after_request
    def handle_after_request(response):  # pylint: disable=unused-variable
        add_version(response)
        set_access_control_header(response)
        return response

    def set_access_control_header(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, registries-trace-id, Account-Id, App-Name, x-apikey, Original-Username, "
            "Original-Sub"
        )

    def add_version(response):  # pylint: disable=unused-variable
        version = get_run_version()
        response.headers["API"] = f"pay_api/{version}"
        return response

    register_shellcontext(app)
    build_cache(app)
    return app


def setup_403_logging(app):
    """Log setup for forbidden."""
    # This is intended for DEV and TEST.
    if app.config.get("ENABLE_403_LOGGING") is True:

        @app.errorhandler(403)
        def handle_403_error(error):
            user_context = _get_context()

            user_name = user_context.user_name[:5] + "..."
            roles = user_context.roles
            app.logger.error(f"403 Forbidden - {request.method} {request.url} - {user_name} - {roles}")

            message = {"message": getattr(error, "message", error.description)}
            headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            return message, error.code, headers


def execute_migrations(app):
    """Execute the database migrations."""
    try:
        upgrade(directory="migrations", revision="head", sql=False, tag=None)
    except Exception as e:  # NOQA pylint: disable=broad-except
        app.logger.disabled = False
        app.logger.error("Error processing migrations:", exc_info=True)
        raise e


def setup_jwt_manager(app, jwt_manager):
    """Use flask app to configure the JWTManager to work for a particular Realm."""

    def get_roles(a_dict):
        return a_dict["realm_access"]["roles"]  # pragma: no cover

    app.config["JWT_ROLE_CALLBACK"] = get_roles

    jwt_manager.init_app(app)


def register_shellcontext(app):
    """Register shell context objects."""
    from pay_api import models  # pylint: disable=import-outside-toplevel

    def shell_context():
        """Shell context objects."""
        return {"app": app, "jwt": jwt, "db": db, "models": models}  # pragma: no cover

    app.shell_context_processor(shell_context)


def build_cache(app):
    """Build cache."""
    cache.init_app(app)
    with app.app_context():
        cache.clear()
        if not app.config.get("TESTING", False):
            try:
                from pay_api.services.code import Code as CodeService  # pylint: disable=import-outside-toplevel

                CodeService.build_all_codes_cache()
            except Exception as e:  # NOQA pylint:disable=broad-except
                app.logger.error("Error on caching ")
                app.logger.error(e)
