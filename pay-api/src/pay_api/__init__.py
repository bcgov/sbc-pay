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

import sentry_sdk  # noqa: I001; pylint: disable=ungrouped-imports,wrong-import-order; conflicts with Flake8
from flask import Flask
from sbc_common_components.exception_handling.exception_handler import ExceptionHandler  # noqa: I001
from sbc_common_components.utils.camel_case_response import convert_to_camel
from sentry_sdk.integrations.flask import FlaskIntegration  # noqa: I001

# import pay_api.config as config
from pay_api import config
from pay_api.config import _Config
from pay_api.services import flags
from pay_api.models import db, ma
from pay_api.utils.auth import jwt
from pay_api.utils.cache import cache
from pay_api.utils.logging import setup_logging
from pay_api.utils.run_version import get_run_version


setup_logging(os.path.join(_Config.PROJECT_ROOT, 'logging.conf'))


def create_app(run_mode=os.getenv('FLASK_ENV', 'production')):
    """Return a configured Flask App using the Factory method."""
    app = Flask(__name__)
    app.config.from_object(config.CONFIGURATION[run_mode])

    flags.init_app(app)
    db.init_app(app)
    ma.init_app(app)

    if run_mode != 'migration':

        # Configure Sentry
        if str(app.config.get('SENTRY_ENABLE')).lower() == 'true':
            if app.config.get('SENTRY_DSN', None):  # pragma: no cover
                sentry_sdk.init(  # pylint: disable=abstract-class-instantiated
                    dsn=app.config.get('SENTRY_DSN'),
                    integrations=[FlaskIntegration()]
                )
        # pylint: disable=import-outside-toplevel
        from pay_api.resources import API_BLUEPRINT, OPS_BLUEPRINT

        app.register_blueprint(API_BLUEPRINT)
        app.register_blueprint(OPS_BLUEPRINT)
        app.after_request(convert_to_camel)

        setup_jwt_manager(app, jwt)

        ExceptionHandler(app)

        @app.after_request
        def add_version(response):  # pylint: disable=unused-variable
            version = get_run_version()
            response.headers['API'] = f'pay_api/{version}'
            return response

        register_shellcontext(app)
        build_cache(app)
    return app


def setup_jwt_manager(app, jwt_manager):
    """Use flask app to configure the JWTManager to work for a particular Realm."""
    def get_roles(a_dict):
        return a_dict['realm_access']['roles']  # pragma: no cover

    app.config['JWT_ROLE_CALLBACK'] = get_roles

    jwt_manager.init_app(app)


def register_shellcontext(app):
    """Register shell context objects."""
    from pay_api import models  # pylint: disable=import-outside-toplevel

    def shell_context():
        """Shell context objects."""
        return {'app': app, 'jwt': jwt, 'db': db, 'models': models}  # pragma: no cover

    app.shell_context_processor(shell_context)


def build_cache(app):
    """Build cache."""
    cache.init_app(app)
    with app.app_context():
        cache.clear()
        if not app.config.get('TESTING', False):
            try:
                from pay_api.services.code import Code as CodeService  # pylint: disable=import-outside-toplevel
                CodeService.build_all_codes_cache()
            except Exception as e:  # NOQA pylint:disable=broad-except
                app.logger.error('Error on caching ')
                app.logger.error(e)
