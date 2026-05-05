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
"""BDD step definitions for fee_schedule_view.feature."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from admin.views.fee_schedule import FeeScheduleConfig
from pay_api.models import FeeSchedule, db
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

scenarios("features/fee_schedule_view.feature")


@pytest.fixture(autouse=True)
def _app_ctx(app):
    with app.app_context():
        yield


@given("the FeeSchedule admin view is loaded")
def load_fee_schedule_view(context):
    """Instantiate FeeScheduleConfig and store it in context."""
    context["view"] = FeeScheduleConfig(FeeSchedule, db.session, endpoint="test_feeschedule")
    context["config_cls"] = FeeScheduleConfig


@when("the FeeSchedule create form is generated")
def generate_fs_create_form(context):
    """Generate the create form."""
    generate_create_form(
        context, ["fee", "future_effective_fee", "priority_fee", "service_fee", "distribution_codes", "gst_added"]
    )


@when("the FeeSchedule edit form is generated")
def generate_fs_edit_form(context):
    """Generate the edit form."""
    generate_edit_form(
        context, ["fee", "future_effective_fee", "priority_fee", "service_fee", "distribution_codes", "gst_added"]
    )


@when("a new FeeSchedule record is saved")
def save_new_fs(context):
    """Save a new record."""
    save_new_record(context)


@when("an existing FeeSchedule record is saved")
def save_existing_fs(context):
    """Save an existing record."""
    save_existing_record(context)


@then("all list columns should be within the configured column_list")
def all_columns_in_config_fs(context):
    """Assert column list."""
    for col_name, _label in context["view"].get_list_columns():
        assert col_name in FeeScheduleConfig.column_list


@then(parsers.parse('the list columns should include "{column}"'))
def list_has_column_fs(context, column):
    """Assert individual column."""
    columns = [name for name, _label in context["view"].get_list_columns()]
    assert column in columns, f"Expected '{column}' in list columns, got: {columns}"


@then(parsers.parse('the default sort column should be "{column}"'))
def default_sort_fs(context, column):
    """Assert default sort."""
    assert context["view"].column_default_sort == column


@then("the audit fields should not be present in the create form")
def audit_fields_absent_fs(context):
    """Assert audit fields are removed from create."""
    assert_audit_fields_absent(context)


@then("the audit fields should be readonly")
def audit_fields_readonly_fs(context):
    """Assert audit fields are readonly."""
    assert_audit_fields_readonly(context)


@then(parsers.parse('the created audit fields should be "{expected_by}" and "{expected_on}"'))
def created_audit_fields_fs(context, expected_by, expected_on):
    """Assert created audit fields."""
    assert_created_fields(context, expected_by, expected_on)


@then(parsers.parse('the updated audit fields should be "{expected_by}" and "{expected_on}"'))
def updated_audit_fields_fs(context, expected_by, expected_on):
    """Assert updated audit fields."""
    assert_updated_fields(context, expected_by, expected_on)
