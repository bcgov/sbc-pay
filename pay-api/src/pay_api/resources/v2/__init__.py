# Copyright © 2026 Province of British Columbia
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
"""Exposes all of the resource endpoints mounted in Flask-Blueprints."""

from typing import Optional

from flask import Flask  # noqa: TC002

from .fas.routing_slip import bp as routing_slip_bp  # noqa: TID252


class V2Endpoint:  # pylint: disable=too-few-public-methods,
    """Setup all the V2 Endpoints."""

    def __init__(self):
        """Create the endpoint setup, without initializations."""
        self.app: Flask | None = None

    def init_app(self, app):
        """Register and initialize the Endpoint setup."""
        if not app:
            raise Exception("Cannot initialize without a Flask App.")  # pylint: disable=broad-exception-raised

        self.app = app
        self.app.register_blueprint(routing_slip_bp)


v2_endpoint = V2Endpoint()
