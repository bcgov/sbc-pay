# Copyright © 2023 Province of British Columbia
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
"""Mounting the end-points."""
from typing import Optional

from flask import Flask

from .v1 import v1_endpoint


class Endpoints:  # pylint: disable=too-few-public-methods
    """Manage the mounting, traversal and redirects for a set of versioned end-points."""

    app: Optional[Flask] = None

    def init_app(self, app: Flask):
        """Initialize the endpoints mapped for all services.

        Manages the versioned routes.
        Sets up redirects based on Accept headers or Versioned routes.
        """
        self.app = app
        self._mount_endpoints()

    def _mount_endpoints(self):
        """Mount the endpoints of the system."""
        v1_endpoint.init_app(self.app)


endpoints = Endpoints()
