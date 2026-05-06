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

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from flask_admin.contrib import sqla
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm.attributes import flag_modified
from wtforms import StringField

from admin import keycloak


class _ReadonlyDateTimeField(StringField):
    """Renders a DateTime column as plain text in BC time (PDT, UTC-7); never writes back to the model on form submit."""

    _PDT = ZoneInfo("Etc/GMT+7")
    _FORMAT = "%Y-%m-%d %H:%M:%S"

    def _value(self):
        if self.data and hasattr(self.data, "strftime"):
            dt = self.data if self.data.tzinfo else self.data.replace(tzinfo=UTC)
            return dt.astimezone(self._PDT).strftime(self._FORMAT)
        return super()._value()

    def populate_obj(self, obj, name):  # noqa: ARG002
        pass  # audit field; value is managed server-side, not via form input


class SecuredView(sqla.ModelView):
    """Wrapper to secure the view with keycloak."""

    # Allow export as a CSV file.
    can_export = False

    _AUDIT_FIELDS = ["created_by", "created_on", "updated_by", "updated_on"]

    form_overrides = {
        "created_on": _ReadonlyDateTimeField,
        "updated_on": _ReadonlyDateTimeField,
    }

    _AUDIT_LABELS = {
        "created_by": "Created By",
        "created_on": "Created On",
        "updated_by": "Updated By",
        "updated_on": "Updated On",
    }

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

    def inaccessible_callback(self, name, **kwargs):  # noqa: ARG002
        """Handle if view is not accessible."""
        if not self.connected:
            self.connected = True
            kc = keycloak.Keycloak(None)
            return kc.get_redirect_url()

        return "not authorized"

    def edit_form(self, obj=None):
        """Make audit fields readonly in edit form."""
        form = super().edit_form(obj)
        for field_name in self._AUDIT_FIELDS:
            if field := getattr(form, field_name, None):
                field.render_kw = {"readonly": True}
        return form

    def create_form(self, obj=None):
        """Remove audit fields from create form because they are auto-populated."""
        form = super().create_form(obj)
        for field_name in self._AUDIT_FIELDS:
            form._fields.pop(field_name, None)
        return form

    def on_model_change(self, form, model, is_created):  # noqa: ARG002
        """Set audit fields from the logged-in OIDC user on every create/edit."""
        kc = keycloak.Keycloak(None)
        username = kc.get_username() or "UNKNOWN"
        name = kc.get_name() or username
        now = datetime.now(tz=UTC)
        if is_created:
            model.created_by = getattr(model, "created_by", None) or username
            model.created_name = getattr(model, "created_name", None) or name
            model.created_on = getattr(model, "created_on", None) or now
        elif self._is_modified(model):
            model.updated_by = username
            model.updated_name = name
            model.updated_on = now
            # Force SQLAlchemy to include these columns in the UPDATE SET clause,
            # preventing the Audit model's onupdate callbacks from firing.
            # Those callbacks use JWT context which is unavailable in Flask-Admin.
            if hasattr(model, "__mapper__"):
                for field in ("updated_by", "updated_name", "updated_on"):
                    flag_modified(model, field)

    def _is_modified(self, model) -> bool:
        """Return True if any non-audit field changed since the model was loaded."""
        try:
            return any(
                attr.history.has_changes() for attr in sa_inspect(model).attrs if attr.key not in self._AUDIT_FIELDS
            )
        except Exception:  # noqa: BLE001
            return True  # non-SA object (e.g. test mocks); assume modified
