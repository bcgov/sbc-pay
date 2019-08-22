# Copyright © 2019 Province of British Columbia
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
"""Resource for Service status endpoints."""
from datetime import datetime
from http import HTTPStatus

from flask import current_app, jsonify
from flask_restplus import Namespace, Resource, cors

from pay_api.services.status_service import StatusService
from pay_api.utils.util import cors_preflight


API = Namespace('status', description='Payment System - Service Status')

STATUS_SERVICE = StatusService()


@cors_preflight('GET')
@API.route('', methods=['GET', 'OPTIONS'])
class ServiceStatus(Resource):
    """Endpoint resource to calculate fee."""

    @staticmethod
    @cors.crossdomain(origin='*')
    @API.response(200, 'OK')
    def get(service_name: str):
        """Get the service schedule and return status and next schedule date/time."""
        current_app.logger.info('<ServiceStatus.get')
        response, status = STATUS_SERVICE.schedule_status(service_name, datetime.utcnow()), HTTPStatus.OK
        current_app.logger.debug('>ServiceStatus.get')
        return jsonify(response), status
