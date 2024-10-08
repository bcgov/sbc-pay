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

from flask_admin.contrib import sqla

from admin import keycloak


class SecuredView(sqla.ModelView):
    """Wrapper to secure the view with keycloak."""

    # Allow export as a CSV file.
    can_export = False

    # Allow the user to change the page size.
    can_set_page_size = True

    column_display_pk = True

    can_delete = False

    @property
    def can_create(self):
        """Return if user can create."""
        return self._has_role(self.edit_role)

    @property
    def can_edit(self):
        """Return if user can edit."""
        return self._has_role(self.edit_role)

    def __init__(  # pylint: disable=too-many-arguments
        self,
        model,
        session,
        name=None,
        category=None,
        endpoint=None,
        url=None,
        static_folder=None,
        menu_class_name=None,
        menu_icon_type=None,
        menu_icon_value=None,
        view_role: str = "admin_view",
        edit_role: str = "admin_edit",
    ):
        """Initialize."""
        super().__init__(
            model,
            session,
            name,
            category,
            endpoint,
            url,
            static_folder,
            menu_class_name,
            menu_icon_type,
            menu_icon_value,
        )
        self.connected = False
        self.view_role = view_role
        self.edit_role = edit_role

    def is_accessible(self):
        """Return True if view is accessible."""
        return self._has_role(self.view_role)

    def _has_role(self, role):
        kc = keycloak.Keycloak(None)
        if not kc.is_logged_in():
            self.connected = False
            return False
        return kc.has_access(role)

    def inaccessible_callback(self, name, **kwargs):
        """Handle if view is not accessible."""
        if not self.connected:
            self.connected = True
            kc = keycloak.Keycloak(None)
            return kc.get_redirect_url()

        return "not authorized"
