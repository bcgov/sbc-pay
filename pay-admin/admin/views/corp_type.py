"""Copyright 2021 Province of British Columbia.

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

from pay_api.models import CorpType, db

from .secured_view import SecuredView


class CorpTypeConfig(SecuredView):
    """Corp Type config."""

    column_list = ["code", "description"]

    column_labels = {
        "code": "Code",
        "description": "Description",
        "bcol_code_full_service_fee": "BCOL Fee Code used for Account transactions - "
        "Service Fee ($1.50 or $1.05 for ESRA)",
        "bcol_code_no_service_fee": "BCOL Fee Code used for Account transactions - Service Fee ($0)",
        "bcol_code_partial_service_fee": "BCOL Fee Code used for Account transactions - Service Fee ($1.00)",
        "bcol_staff_fee_code": "BCOL Fee Code used for Staff transactions. (starts with 'C')",
        "is_online_banking_allowed": "Is Online Banking allowed",
        "product": "Product to map in account products",
    }
    column_searchable_list = ("code",)
    column_sortable_list = ("code",)

    column_default_sort = "code"

    form_choices = {}

    form_columns = edit_columns = [
        "code",
        "description",
        "bcol_code_full_service_fee",
        "bcol_code_no_service_fee",
        "bcol_code_partial_service_fee",
        "bcol_staff_fee_code",
        "is_online_banking_allowed",
        "product",
    ]

    def on_form_prefill(self, form, id):  # pylint:disable=redefined-builtin
        """Prefill overrides."""
        form.code.render_kw = {"readonly": True}


# If this view is going to be displayed for only special roles, do like below
CorpTypeView = CorpTypeConfig(CorpType, db.session)
