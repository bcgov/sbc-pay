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
"""Shared helpers for admin view audit field BDD tests."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from freezegun import freeze_time

AUDIT_FIELDS = ["created_by", "created_on", "updated_by", "updated_on"]


def generate_create_form(context, fields):
    """Generate a create form through SecuredView with a mocked Flask-Admin form."""
    mock_form = MagicMock()
    mock_form._fields = {field: MagicMock() for field in [*fields, *AUDIT_FIELDS]}
    with patch("flask_admin.contrib.sqla.ModelView.create_form", return_value=mock_form):
        context["form"] = context["view"].create_form()


def generate_edit_form(context, fields):
    """Generate an edit form through SecuredView with a mocked Flask-Admin form."""
    mock_form = MagicMock()
    for field_name in [*fields, *AUDIT_FIELDS]:
        field = MagicMock()
        field.render_kw = None
        setattr(mock_form, field_name, field)
    with patch("flask_admin.contrib.sqla.ModelView.edit_form", return_value=mock_form):
        context["form"] = context["view"].edit_form(obj=SimpleNamespace())


def assert_audit_fields_absent(context):
    """Assert audit fields are not present in the form fields."""
    for field_name in AUDIT_FIELDS:
        assert field_name not in context["form"]._fields, f"Audit field '{field_name}' should have been removed"


def assert_audit_fields_readonly(context):
    """Assert audit fields are readonly on the form."""
    for field_name in AUDIT_FIELDS:
        field = getattr(context["form"], field_name)
        assert field.render_kw == {"readonly": True}, (
            f"Expected '{field_name}' to be readonly, got render_kw={field.render_kw}"
        )


def save_new_record(context):
    """Save a new auditable record through the current admin view."""
    model = SimpleNamespace(created_by=None, created_on=None, updated_by=None, updated_on=None)
    with freeze_time(context.get("timestamp", "2024-01-15 10:00:00")):
        context["view"].on_model_change(MagicMock(), model, is_created=True)
    context["model"] = model


def save_existing_record(context):
    """Save an existing auditable record through the current admin view."""
    model = SimpleNamespace(created_by="original", created_on=None, updated_by=None, updated_on=None)
    with freeze_time(context.get("timestamp", "2024-01-15 10:00:00")):
        context["view"].on_model_change(MagicMock(), model, is_created=False)
    context["model"] = model


def assert_created_fields(context, expected_by, expected_on):
    """Assert created audit fields."""
    expected_datetime = datetime.fromisoformat(expected_on.replace(" ", "T")).replace(tzinfo=UTC)
    assert context["model"].created_by == expected_by
    assert context["model"].created_on == expected_datetime
    assert context["model"].updated_by is None
    assert context["model"].updated_on is None


def assert_updated_fields(context, expected_by, expected_on):
    """Assert updated audit fields."""
    expected_datetime = datetime.fromisoformat(expected_on.replace(" ", "T")).replace(tzinfo=UTC)
    assert context["model"].updated_by == expected_by
    assert context["model"].updated_on == expected_datetime
