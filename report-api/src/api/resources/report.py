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
"""Endpoints to check and manage payments."""
from http import HTTPStatus

from flask import abort, request
from flask_restplus import Namespace, Resource
from jinja2 import TemplateNotFound

from api.services import ReportService


API = Namespace('Reports', description='Service - Reports')


@API.route('')
class Report(Resource):
    """Payment endpoint resource."""

    @staticmethod
    def get():
        """Get Status of the report service."""
        return {'message': 'Report generation up and running'}, HTTPStatus.OK

    @staticmethod
    def post():
        """Create a report."""
        request_json = request.get_json()
        template_vars = request_json['template_vars']
        report_name = request_json['report_name']
        pdf = None
        if 'template_name' in request_json:   # Ignore template if template_name is present
            template_name = request_json['template_name']
            try:
                pdf = ReportService.create_report_from_stored_template(template_name, template_vars, report_name)
            except TemplateNotFound:
                abort(HTTPStatus.NOT_FOUND, 'Template not found')

        elif 'template' in request_json:
            pdf = ReportService.create_report_from_template(request_json['template'], template_vars, report_name)

        if pdf is not None:
            response = pdf
        else:
            abort(HTTPStatus.BAD_REQUEST, 'PDF cannot be generate')
        return response
