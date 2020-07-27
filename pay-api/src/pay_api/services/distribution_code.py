# Copyright © 2019 Province of British Columbia
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

from datetime import date
from typing import Dict

from flask import current_app
from sbc_common_components.tracing.service_tracing import ServiceTracing

from pay_api.models import DistributionCode as DistributionCodeModel, DistributionCodeLink as DistributionCodeLinkModel
from pay_api.models.distribution_code import DistributionCodeSchema
from pay_api.models.fee_schedule import FeeScheduleSchema


@ServiceTracing.trace(ServiceTracing.enable_tracing, ServiceTracing.should_be_tracing)
class DistributionCode:  # pylint: disable=too-many-instance-attributes
    """Service to manage distribution code related operations."""

    def __init__(self):
        """Return a Service object."""
        self.__dao = None
        self._distribution_code_id: int = None
        self._memo_name: str = None
        self._service_fee_memo_name: str = None

        self._client: str = None
        self._responsibility_centre: str = None
        self._service_line: str = None
        self._stob: str = None
        self._project_code: str = None

        self._service_fee_client: str = None
        self._service_fee_responsibility_centre: str = None
        self._service_fee_line: str = None
        self._service_fee_stob: str = None
        self._service_fee_project_code: str = None

        self._start_date: date = None
        self._end_date: date = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = DistributionCodeModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao = value

        self._distribution_code_id: int = self._dao.distribution_code_id
        self._memo_name: str = self._dao.memo_name
        self._service_fee_memo_name: str = self._dao.service_fee_memo_name

        self._client: str = self._dao.client
        self._responsibility_centre: str = self._dao.responsibility_centre
        self._service_line: str = self._dao.service_line
        self._stob: str = self._dao.stob
        self._project_code: str = self._dao.project_code

        self._service_fee_client: str = self._dao.service_fee_client
        self._service_fee_responsibility_centre: str = self._dao.service_fee_responsibility_centre
        self._service_fee_line: str = self._dao.service_fee_line
        self._service_fee_stob: str = self._dao.service_fee_stob
        self._service_fee_project_code: str = self._dao.service_fee_project_code

        self._start_date: date = self._dao.start_date
        self._end_date: date = self._dao.end_date

    @property
    def end_date(self):
        """Return the end_date."""
        return self._end_date

    @end_date.setter
    def end_date(self, value: date):
        """Set the end_date."""
        self._end_date = value
        self._dao.end_date = value

    @property
    def start_date(self):
        """Return the start_date."""
        return self._start_date

    @start_date.setter
    def start_date(self, value: date):
        """Set the start_date."""
        self._start_date = value
        self._dao.start_date = value

    @property
    def service_fee_stob(self):
        """Return the _service_fee_stob."""
        return self._service_fee_stob

    @service_fee_stob.setter
    def service_fee_stob(self, value: str):
        """Set the service_fee_stob."""
        self._service_fee_stob = value
        self._dao.service_fee_stob = value

    @property
    def service_fee_line(self):
        """Return the service_fee_centre."""
        return self._service_fee_line

    @service_fee_line.setter
    def service_fee_line(self, value: str):
        """Set the service_fee_line."""
        self._service_fee_line = value
        self._dao.service_fee_line = value

    @property
    def service_fee_responsibility_centre(self):
        """Return the service_fee_memo_name."""
        return self._service_fee_responsibility_centre

    @service_fee_responsibility_centre.setter
    def service_fee_responsibility_centre(self, value: str):
        """Set the service_fee_responsibility_centre."""
        self._service_fee_responsibility_centre = value
        self._dao.service_fee_responsibility_centre = value

    @property
    def service_fee_memo_name(self):
        """Return the service_fee_memo_name."""
        return self._service_fee_memo_name

    @service_fee_memo_name.setter
    def service_fee_memo_name(self, value: str):
        """Set the service_fee_memo_name."""
        self._service_fee_memo_name = value
        self._dao.service_fee_memo_name = value

    @property
    def stob(self):
        """Return the stob."""
        return self._stob

    @stob.setter
    def stob(self, value: str):
        """Set the stob."""
        self._stob = value
        self._dao.stob = value

    @property
    def responsibility_centre(self):
        """Return the responsibility_centre."""
        return self._responsibility_centre

    @responsibility_centre.setter
    def responsibility_centre(self, value: str):
        """Set the responsibility_centre."""
        self._responsibility_centre = value
        self._dao.responsibility_centre = value

    @property
    def service_line(self):
        """Return the service_line."""
        return self._service_line

    @service_line.setter
    def service_line(self, value: str):
        """Set the service_line."""
        self._service_line = value
        self._dao.service_line = value

    @property
    def client(self):
        """Return the client."""
        return self._client

    @client.setter
    def client(self, value: str):
        """Set the client."""
        self._client = value
        self._dao.client = value

    @property
    def project_code(self):
        """Return the project_code."""
        return self._project_code

    @project_code.setter
    def project_code(self, value: str):
        """Set the project_code."""
        self._project_code = value
        self._dao.project_code = value

    @property
    def service_fee_client(self):
        """Return the service_fee_client."""
        return self._service_fee_client

    @service_fee_client.setter
    def service_fee_client(self, value: str):
        """Set the service_fee_client."""
        self._service_fee_client = value
        self._dao.service_fee_client = value

    @property
    def service_fee_project_code(self):
        """Return the service_fee_project_code."""
        return self._service_fee_project_code

    @service_fee_project_code.setter
    def service_fee_project_code(self, value: str):
        """Set the service_fee_project_code."""
        self._service_fee_project_code = value
        self._dao.service_fee_project_code = value

    def save(self):
        """Save the distribution code information."""
        return self._dao.save()

    @staticmethod
    def find_all():
        """Find all distribution codes valid today."""
        current_app.logger.debug('<find_all')
        data = {
            'items': []
        }
        distribution_codes = DistributionCodeModel.find_all()
        distribution_code_schema = DistributionCodeSchema()
        data['items'] = distribution_code_schema.dump(distribution_codes, many=True)
        current_app.logger.debug('>find_all')
        return data

    @staticmethod
    def find_by_id(identifier: int):
        """Find distribution code by id."""
        current_app.logger.debug('<find_by_id')
        distribution_code = DistributionCodeModel.find_by_id(identifier=identifier)
        distribution_code_schema = DistributionCodeSchema()
        current_app.logger.debug('>find_by_id')
        return distribution_code_schema.dump(distribution_code, many=False)

    @staticmethod
    def find_fee_schedules_by_distribution_id(distribution_id: int):
        """Find distribution schedules by code by id."""
        current_app.logger.debug('<find_fee_schedule_by_distribution_id')
        data = {
            'items': []
        }

        fee_schedules = DistributionCodeLinkModel.find_fee_schedules_by_distribution_id(
            distribution_code_id=distribution_id)
        fee_schedule_schema = FeeScheduleSchema()
        data['items'] = fee_schedule_schema.dump(fee_schedules, many=True)
        current_app.logger.debug('>find_by_id')
        return data

    @staticmethod
    def save_or_update(distribution_details: Dict, dist_id: int = None):
        """Save distribution."""
        current_app.logger.debug('<save')

        dist_code_svc = DistributionCode()
        if dist_id is not None:
            dist_code_dao = DistributionCodeModel.find_by_id(dist_id)
            dist_code_svc._dao = dist_code_dao  # pylint: disable=protected-access

        dist_code_svc.end_date = distribution_details.get('endDate', None)
        dist_code_svc.start_date = distribution_details.get('startDate', date.today())

        dist_code_svc.client = distribution_details.get('client', None)
        dist_code_svc.responsibility_centre = distribution_details.get('responsibilityCentre', None)
        dist_code_svc.service_line = distribution_details.get('serviceLine', None)
        dist_code_svc.stob = distribution_details.get('stob', None)
        dist_code_svc.project_code = distribution_details.get('projectCode', None)

        dist_code_svc.service_fee_client = distribution_details.get('serviceFeeClient', None)
        dist_code_svc.service_fee_responsibility_centre = distribution_details.get('serviceFeeResponsibilityCentre',
                                                                                   None)
        dist_code_svc.service_fee_line = distribution_details.get('serviceFeeLine', None)
        dist_code_svc.service_fee_stob = distribution_details.get('serviceFeeStob', None)
        dist_code_svc.service_fee_project_code = distribution_details.get('serviceFeeProjectCode', None)

        dist_code_dao = dist_code_svc.save()
        distribution_code_schema = DistributionCodeSchema()
        current_app.logger.debug('>find_by_id')
        return distribution_code_schema.dump(dist_code_dao, many=False)

    @staticmethod
    def create_link(fee_schedules: Dict, dist_id: int):
        """Create link between distribution and fee schedule."""
        current_app.logger.debug('<create_link')
        links: list = []
        for fee_schedule in fee_schedules:
            link = DistributionCodeLinkModel()
            link.distribution_code_id = dist_id
            link.fee_schedule_id = fee_schedule.get('feeScheduleId')
            links.append(link)

        DistributionCodeLinkModel.bulk_save_links(links)
        current_app.logger.debug('>create_link')
