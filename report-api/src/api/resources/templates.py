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

from flask import Response, abort, request
from flask_restx import Namespace, Resource
from jinja2 import TemplateNotFound

from api.services.template_service import TemplateService


API = Namespace('payments', description='Service - Payments')


@API.route('')
class Templates(Resource):
    """Payment endpoint resource."""

    @staticmethod
    def get():
        """Return all report-templates or returns specific html of a template."""
        template_name = request.args.get('name')
        if template_name is None:
            templates = TemplateService.find_all_templates()
            response = {'report-templates': templates}
        else:
            try:
                html = TemplateService.get_stored_template(request.args.get('name'))
                response = Response(html, HTTPStatus.OK)
                response.headers.set('Content-Disposition', 'attachment', filename={request.args.get('name')})
                response.headers.set('Content-Type', 'application/html')
            except TemplateNotFound:
                abort(HTTPStatus.NOT_FOUND, 'Template not found')
        return response
