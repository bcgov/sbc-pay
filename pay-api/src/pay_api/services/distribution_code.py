# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Service to manage Fee Calculation."""

from __future__ import annotations

from datetime import UTC, datetime

from dateutil import parser
from flask import current_app

from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import DistributionCodeLink as DistributionCodeLinkModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models.distribution_code import DistributionCodeSchema
from pay_api.models.fee_schedule import FeeScheduleSchema


class DistributionCode:
    """Service to manage distribution code related operations."""

    @staticmethod
    def asdict(dao):
        """Return the distribution code as a python dict."""
        distribution_schema = DistributionCodeSchema()
        d = distribution_schema.dump(dao)
        return d

    @staticmethod
    def find_all():
        """Find all distribution codes valid today."""
        current_app.logger.debug("<find_all")
        data = {"items": []}
        distribution_codes = DistributionCodeModel.find_all()
        distribution_code_schema = DistributionCodeSchema()
        data["items"] = distribution_code_schema.dump(distribution_codes, many=True)
        current_app.logger.debug(">find_all")
        return data

    @staticmethod
    def find_by_id(identifier: int):
        """Find distribution code by id."""
        current_app.logger.debug(f"<find_by_id, {identifier}")
        distribution_code = DistributionCodeModel.find_by_id(identifier=identifier)
        distribution_code_schema = DistributionCodeSchema()
        current_app.logger.debug(">find_by_id")
        return distribution_code_schema.dump(distribution_code, many=False)

    @staticmethod
    def find_active_by_account_id(account_id: int) -> DistributionCode:
        """Find active distribution code by account_id."""
        current_app.logger.debug(f"<find_active_by_account_id, {account_id}")
        distribution_code = DistributionCodeModel.find_by_active_for_account(account_id)
        current_app.logger.debug(">find_active_by_account_id")
        return distribution_code

    @staticmethod
    def find_fee_schedules_by_distribution_id(distribution_id: int):
        """Find distribution schedules by code by id."""
        current_app.logger.debug("<find_fee_schedule_by_distribution_id")
        data = {"items": []}

        fee_schedules = DistributionCodeLinkModel.find_fee_schedules_by_distribution_id(
            distribution_code_id=distribution_id
        )
        fee_schedule_schema = FeeScheduleSchema()
        data["items"] = fee_schedule_schema.dump(fee_schedules, many=True)
        current_app.logger.debug(">find_fee_schedules_by_distribution_id")
        return data

    @staticmethod
    def save_or_update(distribution_details: dict, dist_id: int = None):
        """Save distribution."""
        current_app.logger.debug("<save_or_update")

        dist_code_dao = DistributionCodeModel()
        if dist_id is not None:
            dist_code_dao = DistributionCodeModel.find_by_id(dist_id)

        if distribution_details.get("endDate", None):
            dist_code_dao.end_date = parser.parse(distribution_details.get("endDate"))

        if distribution_details.get("startDate", None):
            dist_code_dao.start_date = parser.parse(distribution_details.get("startDate"))
        else:
            dist_code_dao.start_date = datetime.now(tz=UTC).date()

        _has_code_changes: bool = (
            dist_code_dao.client != distribution_details.get("client", None)
            or dist_code_dao.responsibility_centre != distribution_details.get("responsibilityCentre", None)
            or dist_code_dao.service_line != distribution_details.get("serviceLine", None)
            or dist_code_dao.project_code != distribution_details.get("projectCode", None)
            or dist_code_dao.service_fee_distribution_code_id
            != distribution_details.get("serviceFeeDistributionCodeId", None)
        )

        dist_code_dao.client = distribution_details.get("client", None)
        dist_code_dao.name = distribution_details.get("name", None)
        dist_code_dao.responsibility_centre = distribution_details.get("responsibilityCentre", None)
        dist_code_dao.service_line = distribution_details.get("serviceLine", None)
        dist_code_dao.stob = distribution_details.get("stob", None)
        dist_code_dao.project_code = distribution_details.get("projectCode", None)
        dist_code_dao.service_fee_distribution_code_id = distribution_details.get("serviceFeeDistributionCodeId", None)
        dist_code_dao.service_fee_gst_distribution_code_id = distribution_details.get(
            "serviceFeeGstDistributionCodeId", None
        )
        dist_code_dao.statutory_fees_gst_distribution_code_id = distribution_details.get(
            "statutoryFeesGstDistributionCodeId", None
        )
        dist_code_dao.disbursement_distribution_code_id = distribution_details.get(
            "disbursementDistributionCodeId", None
        )
        dist_code_dao.account_id = distribution_details.get("accountId", None)

        if _has_code_changes and dist_id is not None:
            # Update all invoices which used this distribution for updating revenue account details
            # If this is a service fee distribution, then find all distribution which uses this and update them.
            InvoiceModel.update_invoices_for_revenue_updates(dist_id)
            for dist in DistributionCodeModel.find_by_service_fee_distribution_id(dist_id):
                InvoiceModel.update_invoices_for_revenue_updates(dist.distribution_code_id)

        # Reset stop jv for every dave.
        dist_code_dao.stop_ejv = False
        dist_code_dao = dist_code_dao.save()

        distribution_code_schema = DistributionCodeSchema()
        current_app.logger.debug(">save_or_update")
        return distribution_code_schema.dump(dist_code_dao, many=False)

    @staticmethod
    def create_link(fee_schedules: dict, dist_id: int):
        """Create link between distribution and fee schedule."""
        current_app.logger.debug("<create_link")
        links = []
        for fee_schedule in fee_schedules:
            link = DistributionCodeLinkModel()
            link.distribution_code_id = dist_id
            link.fee_schedule_id = fee_schedule.get("feeScheduleId")
            links.append(link)

        DistributionCodeLinkModel.bulk_save_links(links)
        current_app.logger.debug(">create_link")
