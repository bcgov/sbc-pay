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

from pay_api.models import DistributionCode, PaymentAccount, db

from .secured_view import SecuredView


class DistributionCodeConfig(SecuredView):
    """Distribution Code config."""

    column_list = [
        "name",
        "client",
        "responsibility_centre",
        "service_line",
        "stob",
        "project_code",
        "start_date",
        "end_date",
    ]

    column_labels = {
        "name": "Name",
        "client": "Client Code",
        "responsibility_centre": "Responsibility Centre",
        "service_line": "Service Line",
        "stob": "STOB",
        "project_code": "Project Code",
        "start_date": "Effective start date",
        "end_date": "Effective end date",
        "stop_ejv": "Suspend EJV",
        "service_fee_distribution_code": "Service Fee Distribution Code",
        "disbursement_distribution_code": "Disbursement Distribution Code",
        "statutory_fees_gst_distribution_code": "Statutory Fees GST Distribution Code",
        "service_fee_gst_distribution_code": "Service Fee GST Distribution Code",
        "account": "Account (For ministry government accounts)",
    }
    column_searchable_list = (
        "name",
        "stop_ejv",
        "client",
        "responsibility_centre",
        "service_line",
        "stob",
        "project_code",
    )
    column_sortable_list = ("name",)

    column_default_sort = "name"

    form_args = {
        "account": {
            "query_factory": lambda: db.session.query(PaymentAccount)
            .filter(PaymentAccount.payment_method == "EJV")
            .all()
        }
    }

    form_columns = edit_columns = [
        "name",
        "stop_ejv",
        "client",
        "responsibility_centre",
        "service_line",
        "stob",
        "project_code",
        "start_date",
        "end_date",
        "stop_ejv",
        "service_fee_distribution_code",
        "disbursement_distribution_code",
        "statutory_fees_gst_distribution_code",
        "service_fee_gst_distribution_code",
        "account",
    ]

    def edit_form(self, obj=None):
        """Edit form overrides."""
        form = super().edit_form(obj)
        form.account.render_kw = {"disabled": True}

        return form

    def create_form(self, obj=None):
        """Create form overrides."""
        form = super().create_form(obj)
        return form

    def on_model_change(self, form, model, is_created):
        """Trigger on model change."""
        model.created_by = model.created_by or "SYSTEM"
        if is_created:
            model.updated_by = "SYSTEM"


# If this view is going to be displayed for only special roles, do like below
DistributionCodeView = DistributionCodeConfig(DistributionCode, db.session)
