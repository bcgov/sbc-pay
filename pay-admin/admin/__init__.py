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
from pay_api.models import FilingType, db, ma
from pay_api.utils.logging import setup_logging

from admin import config
from admin.config import _Config
from admin.views import CodeConfig, CorpTypeView, DistributionCodeView, FeeCodeView, FeeScheduleView, IndexView

from .keycloak import Keycloak


setup_logging(os.path.join(_Config.PROJECT_ROOT, 'logging.conf'))


def create_app(run_mode=os.getenv('DEPLOYMENT_ENV', 'production')):
    """Return a configured Flask App using the Factory method."""
    app = Flask(__name__)
    app.config.from_object(config.CONFIGURATION[run_mode])

    db.init_app(app)
    ma.init_app(app)

    init_flask_admin(app)
    Keycloak(app)

    @app.route('/')
    def index():
        return redirect('/admin/feecode/')

    return app


def init_flask_admin(app):
    """Initialize flask admin and it's views."""
    flask_admin = Admin(app, name='Fee Admin', template_mode='bootstrap4', index_view=IndexView())
    flask_admin.add_view(FeeCodeView)
    flask_admin.add_view(CorpTypeView)
    flask_admin.add_view(CodeConfig(FilingType, db.session))
    flask_admin.add_view(FeeScheduleView)
    flask_admin.add_view(DistributionCodeView)
    return flask_admin
