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
"""BDD step definitions for distribution_code_view.feature."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time
from pytest_bdd import given, parsers, scenarios, then, when

from admin.keycloak import Keycloak
from admin.views.distribution_code import DistributionCodeConfig
from pay_api.models import DistributionCode, db
from tests.fake_oidc import FakeOidc

scenarios("features/distribution_code_view.feature")

_AUDIT_FIELDS = ["created_by", "created_on", "updated_by", "updated_on"]


@pytest.fixture(autouse=True)
def _app_ctx(app):
    with app.app_context():
        yield


@pytest.fixture(autouse=True)
def reset_oidc():
    """Fresh FakeOidc for every test so user_getfield can be overridden cleanly."""
    Keycloak._oidc = FakeOidc()  # noqa: SLF001
    yield


@given("the DistributionCode admin view is loaded")
def load_distribution_code_view(context):
    """Instantiate DistributionCodeConfig and store it in context."""
    context["view"] = DistributionCodeConfig(DistributionCode, db.session, endpoint="test_dc_unit")
    context["config_cls"] = DistributionCodeConfig


@when("the DistributionCode create form is generated")
def generate_dc_create_form(context):
    """Set a mock form."""
    mock_form = MagicMock()
    mock_form._fields = {field: MagicMock() for field in ["name", *_AUDIT_FIELDS]}
    with patch("admin.views.secured_view.SecuredView.create_form", return_value=mock_form):
        context["form"] = context["view"].create_form()


@when("the DistributionCode edit form is generated")
def generate_dc_edit_form(context):
    """Set a generated form for edit."""
    mock_form = MagicMock()
    mock_form.account.render_kw = None
    for field_name in _AUDIT_FIELDS:
        field = MagicMock()
        field.render_kw = None
        setattr(mock_form, field_name, field)
    obj = SimpleNamespace(distribution_code_id=None)
    with patch("admin.views.secured_view.SecuredView.edit_form", return_value=mock_form):
        context["form"] = context["view"].edit_form(obj=obj)


@when("a new distribution code record is saved")
def save_new_dc(context):
    """Set a create form."""
    model = SimpleNamespace(created_by=None, created_on=None, updated_by=None, updated_on=None)
    with freeze_time(context.get("timestamp", "2024-01-15 10:00:00")):
        context["view"].on_model_change(MagicMock(), model, is_created=True)
    context["model"] = model


@when("an existing distribution code record is saved")
def save_existing_dc(context):
    """Set existing distribution code."""
    model = SimpleNamespace(created_by="original", created_on=None, updated_by=None, updated_on=None)
    with freeze_time(context.get("timestamp", "2024-01-15 10:00:00")):
        context["view"].on_model_change(MagicMock(), model, is_created=False)
    context["model"] = model


@then("all list columns should be within the configured column_list")
def all_columns_in_config_dc(context):
    """Assert all list columns are in the declared column_list."""
    for col_name, _label in context["view"].get_list_columns():
        assert col_name in DistributionCodeConfig.column_list


@then(parsers.parse('the list columns should include "{column}"'))
def list_has_column_dc(context, column):
    """Assert list view shows the key GL code fields."""
    columns = [name for name, _label in context["view"].get_list_columns()]
    assert column in columns, f"Expected '{column}' in list columns, got: {columns}"


@then(parsers.parse('the default sort column should be "{column}"'))
def default_sort_dc(context, column):
    """Assert default sort."""
    assert context["view"].column_default_sort == column


@then("the audit fields should not be present in the create form")
def audit_fields_absent_dc(context):
    """Assert audit fields are not present in create."""
    for field in _AUDIT_FIELDS:
        assert field not in context["form"]._fields, f"Audit field '{field}' should have been removed"


@then("the account field should be disabled")
def account_disabled_dc(context):
    """Assert account field is disabled."""
    render_kw = context["form"].account.render_kw
    assert render_kw is not None
    assert render_kw.get("disabled") is True


@then("the audit fields should be readonly")
def audit_fields_readonly_dc(context):
    """Assert readonly audit columns."""
    for field_name in _AUDIT_FIELDS:
        field = getattr(context["form"], field_name)
        assert field.render_kw == {"readonly": True}, (
            f"Expected '{field_name}' to be readonly, got render_kw={field.render_kw}"
        )


@then(parsers.parse('the distribution code created_by should be "{expected}"'))
def dc_created_by_is(context, expected):
    """Assert created by."""
    assert context["model"].created_by == expected


@then(parsers.parse('the distribution code created_on should be "{ts}"'))
def dc_created_on_is(context, ts):
    """Assert created on."""
    expected = datetime.fromisoformat(ts.replace(" ", "T")).replace(tzinfo=UTC)
    assert context["model"].created_on == expected


@then("the distribution code updated fields should not be set")
def dc_updated_not_set(context):
    """Assert updated is not set on create."""
    assert context["model"].updated_by is None
    assert context["model"].updated_on is None


@then(parsers.parse('the distribution code updated_by should be "{expected}"'))
def dc_updated_by_is(context, expected):
    """Assert updated is set on update."""
    assert context["model"].updated_by == expected


@then(parsers.parse('the distribution code updated_on should be "{ts}"'))
def dc_updated_on_is(context, ts):
    """Assert updated on is set on update."""
    expected = datetime.fromisoformat(ts.replace(" ", "T")).replace(tzinfo=UTC)
    assert context["model"].updated_on == expected
