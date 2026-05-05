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
"""BDD step definitions for fee_code_view.feature."""

from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from admin.views.fee_code import FeeCodeConfig
from pay_api.models import FeeCode, db
from tests.utilities.admin_view_audit_helpers import (
    assert_audit_fields_absent,
    assert_audit_fields_readonly,
    assert_created_fields,
    assert_updated_fields,
    generate_create_form,
    generate_edit_form,
    save_existing_record,
    save_new_record,
)

scenarios("features/fee_code_view.feature")


@pytest.fixture(autouse=True)
def _app_ctx(app):
    with app.app_context():
        yield


@given("the FeeCode admin view is loaded")
def load_fee_code_view(context):
    """Set the view."""
    context["view"] = FeeCodeConfig(FeeCode, db.session, endpoint="test_feecode")
    context["config_cls"] = FeeCodeConfig


@when("the edit form is prefilled for an existing record")
def prefill_form_fc(context):
    """Set the edit form."""
    mock_form = MagicMock()
    mock_form.code.render_kw = None
    context["view"].on_form_prefill(mock_form, id="any")
    context["form"] = mock_form


@when("the FeeCode create form is generated")
def generate_fc_create_form(context):
    """Generate the create form."""
    generate_create_form(context, ["code", "amount"])


@when("the FeeCode edit form is generated")
def generate_fc_edit_form(context):
    """Generate the edit form."""
    generate_edit_form(context, ["code", "amount"])


@when("a new FeeCode record is saved")
def save_new_fc(context):
    """Save a new record."""
    save_new_record(context)


@when("an existing FeeCode record is saved")
def save_existing_fc(context):
    """Save an existing record."""
    save_existing_record(context)


@then("all list columns should be within the configured column_list")
def all_columns_in_config_fc(context):
    """Assert all columns listed."""
    for col_name, _label in context["view"].get_list_columns():
        assert col_name in FeeCodeConfig.column_list


@then(parsers.parse('the list columns should include "{column}"'))
def list_has_column_fc(context, column):
    """Assert individual column."""
    columns = [name for name, _label in context["view"].get_list_columns()]
    assert column in columns, f"Expected '{column}' in list columns, got: {columns}"


@then(parsers.parse('the default sort column should be "{column}"'))
def default_sort_fc(context, column):
    """Assert default sort."""
    assert context["view"].column_default_sort == column


@then("the code field should be readonly")
def code_is_readonly_fc(context):
    """Assert readonly column."""
    assert context["form"].code.render_kw == {"readonly": True}


@then("the audit fields should not be present in the create form")
def audit_fields_absent_fc(context):
    """Assert audit fields are removed from create."""
    assert_audit_fields_absent(context)


@then("the audit fields should be readonly")
def audit_fields_readonly_fc(context):
    """Assert audit fields are readonly."""
    assert_audit_fields_readonly(context)


@then(parsers.parse('the created audit fields should be "{expected_by}" and "{expected_on}"'))
def created_audit_fields_fc(context, expected_by, expected_on):
    """Assert created audit fields."""
    assert_created_fields(context, expected_by, expected_on)


@then(parsers.parse('the updated audit fields should be "{expected_by}" and "{expected_on}"'))
def updated_audit_fields_fc(context, expected_by, expected_on):
    """Assert updated audit fields."""
    assert_updated_fields(context, expected_by, expected_on)
