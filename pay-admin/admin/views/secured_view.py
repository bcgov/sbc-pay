"""Copyright 2018 Province of British Columbia.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from flask import request
from flask_admin.contrib import sqla

from admin import keycloak


class SecuredView(sqla.ModelView):
    """Wrapper to secure the view with keycloak."""

    def __init__(self, model, session,  # pylint: disable=too-many-arguments
                 name=None, category=None, endpoint=None, url=None, static_folder=None,
                 menu_class_name=None, menu_icon_type=None, menu_icon_value=None, allowed_role: str = 'admin_view'):
        """Initialize."""
        print('2222222')
        super().__init__(model, session,
                         name, category, endpoint, url, static_folder,
                         menu_class_name, menu_icon_type, menu_icon_value)
        self.connected = False
        self.allowed_role = allowed_role

    def is_accessible(self):
        """Return True if view is accessible."""
        kc = keycloak.Keycloak(None)
        print(' kc.is_logged_in() ', kc.is_logged_in())
        if not kc.is_logged_in():
            self.connected = False
            return False

        return kc.has_access(self.allowed_role)

    def inaccessible_callback(self, name, **kwargs):
        """Handle if view is not accessible."""
        if not self.connected:
            self.connected = True
            kc = keycloak.Keycloak(None)
            return kc.get_redirect_url(request.url)

        return 'not authorized'
