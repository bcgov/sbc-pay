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
"""The report Microservice.This module is the API for the Legal Entity system."""

import os

from flask import Flask

import config
from api import models
from api.utils.logging import setup_logging
from api.utils.run_version import get_run_version


setup_logging(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logging.conf'))  # important to do this first

# lower case name as used by convention in most Flask apps
tracing = None  # pylint: disable=invalid-name
TEMPLATE_FOLDER_PATH = 'report-templates/'


def create_app(run_mode=os.getenv('FLASK_ENV', 'production')):
    """Return a configured Flask App using the Factory method."""
    app = Flask(__name__)
    app.config.from_object(config.CONFIGURATION[run_mode])

    # initialize tracer
    global tracing  # pylint:  disable=global-statement,invalid-name
    global TEMPLATE_FOLDER_PATH  # pylint:  disable=global-statement
    TEMPLATE_FOLDER_PATH = 'report-templates/'

    from api.resources import API_BLUEPRINT, OPS_BLUEPRINT

    app.register_blueprint(API_BLUEPRINT)
    app.register_blueprint(OPS_BLUEPRINT)

    @app.after_request
    def add_version(response):  # pylint:  disable=unused-variable
        version = get_run_version()
        response.headers['API'] = f'report_api/{version}'
        return response

    register_shellcontext(app)

    return app


def register_shellcontext(app):
    """Register shell context objects."""
    def shell_context():
        """Shell context objects."""
        return {'app': app, 'models': models}  # pragma: no cover

    app.shell_context_processor(shell_context)
