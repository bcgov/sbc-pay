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

from pay_api.models import FeeSchedule, db

from .secured_view import SecuredView


class FeeScheduleConfig(SecuredView):
    """Fee Schedule config."""

    column_list = [
        "corp_type_code",
        "filing_type_code",
        "fee",
        "future_effective_fee",
        "priority_fee",
        "service_fee",
        "variable",
        "show_on_pricelist",
        "gst_added",
    ]

    column_labels = {
        "corp_type": "Corp Type",
        "corp_type_code": "Corp Type",
        "filing_type": "Filing Type",
        "filing_type_code": "Filing Type",
        "fee": "Filing Fee",
        "fee_start_date": "Fee effective start date",
        "fee_end_date": "Fee End Date",
        "future_effective_fee": "Future Effective Fee",
        "priority_fee": "Priority Fee",
        "service_fee": "Service Fee",
        "distribution_codes": "Distribution Code",
        "variable": "Variable Fee Flag",
        "show_on_pricelist": "Show on Price List",
        "gst_added": "GST Added to Price",
    }
    column_searchable_list = ("corp_type_code", "filing_type_code")
    column_sortable_list = ("corp_type_code",)

    column_default_sort = "corp_type_code"

    form_args = {}

    form_columns = [
        "corp_type",
        "filing_type",
        "fee",
        "fee_start_date",
        "fee_end_date",
        "future_effective_fee",
        "priority_fee",
        "service_fee",
        "distribution_codes",
        "variable",
        "show_on_pricelist",
        "gst_added",
    ]
    edit_columns = [
        "corp_type",
        "filing_type",
        "fee_start_date",
        "fee_end_date",
        "priority_fee",
        "service_fee",
        "distribution_codes",
        "show_on_pricelist",
        "gst_added",
    ]

    @staticmethod
    def _change_labels(form):
        form.fee.label.text = "Filing Fee (Starts with 'EN')"
        form.future_effective_fee.label.text = "Future Effective Fee (Starts with 'FUT')"
        form.priority_fee.label.text = "Priority Fee (Starts with 'PRI')"
        form.service_fee.label.text = "Service Fee (Starts with 'TRF')"
        form.distribution_codes.label.text = "Distribution Code (Mandatory for non-zero fees)"
        form.gst_added.label.text = "GST Added to Price"

    def edit_form(self, obj=None):
        """Edit form overrides."""
        form = super().edit_form(obj)
        self._change_labels(form)
        return form

    def create_form(self, obj=None):
        """Create form overrides."""
        form = super().create_form(obj)
        self._change_labels(form)
        return form


# If this view is going to be displayed for only special roles, do like below
FeeScheduleView = FeeScheduleConfig(FeeSchedule, db.session)
