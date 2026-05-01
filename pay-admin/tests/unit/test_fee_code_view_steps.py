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


@then("all list columns should be within the configured column_list")
def all_columns_in_config_fc(context):
    """Assert all columns listed."""
    for col_name, _label in context["view"].get_list_columns():
        assert col_name in FeeCodeConfig.column_list


@then(parsers.parse('the list columns should include "{column}"'))
def list_has_column_fc(context, column):
    """Assert inidividual column."""
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
