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

from flask import Flask
from sbc_common_components.exception_handling.exception_handler import ExceptionHandler  # noqa: I001
from sbc_common_components.utils.camel_case_response import convert_to_camel

from bcol_api import config
from bcol_api.config import _Config
from bcol_api.resources import API_BLUEPRINT, OPS_BLUEPRINT
from bcol_api.utils.auth import jwt
from bcol_api.utils.logging import setup_logging
from bcol_api.utils.run_version import get_run_version

setup_logging(os.path.join(_Config.PROJECT_ROOT, "logging.conf"))  # important to do this first


def create_app(run_mode=None):
    """Return a configured Flask App using the Factory method."""
    if run_mode is None:
        run_mode = os.getenv("FLASK_ENV", "production")
    app = Flask(__name__)
    app.config.from_object(config.CONFIGURATION[run_mode])

    app.register_blueprint(API_BLUEPRINT)
    app.register_blueprint(OPS_BLUEPRINT)
    app.after_request(convert_to_camel)

    setup_jwt_manager(app, jwt)

    ExceptionHandler(app)

    @app.after_request
    def add_version(response):  # pylint: disable=unused-variable
        version = get_run_version()
        response.headers["API"] = f"bcol_api/{version}"
        return response

    register_shellcontext(app)

    return app


def setup_jwt_manager(app, jwt_manager):
    """Use flask app to configure the JWTManager to work for a particular Realm."""

    def get_roles(a_dict):
        return a_dict["realm_access"]["roles"]  # pragma: no cover

    app.config["JWT_ROLE_CALLBACK"] = get_roles

    jwt_manager.init_app(app)


def register_shellcontext(app):
    """Register shell context objects."""

    def shell_context():
        """Shell context objects."""
        return {"app": app, "jwt": jwt}  # pragma: no cover

    app.shell_context_processor(shell_context)
