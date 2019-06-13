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
from flask_restplus import Namespace, Resource
from flask import request, Response
from report_api.services.template_service import TemplateService


API = Namespace('payments', description='Service - Payments')


@API.route('')
class Templates(Resource):
    """Payment endpoint resource."""

    @staticmethod
    def get():
        """ Return all report-templates or returns specific html of a template"""
        template_name = request.args.get('templatename')
        if template_name is None:
            templates = TemplateService.find_all_templates()
            response = {'report-templates': templates}
        else:
            html = TemplateService.get_stored_template(request.args.get('templatename'))
            print(html)
            response = Response(html, HTTPStatus.OK)
            response.headers.set('Content-Disposition', 'attachment', filename={request.args.get('templatename')})
            response.headers.set('Content-Type', 'application/html')
        return response, HTTPStatus.OK
