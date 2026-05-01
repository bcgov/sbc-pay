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
from pytest_bdd import given, parsers, scenarios, then

from admin.views.fee_schedule import FeeScheduleConfig
from pay_api.models import FeeSchedule, db

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
