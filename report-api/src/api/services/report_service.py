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

"""Service to  manage report-templates"""

import base64
from flask_weasyprint import HTML, render_pdf
from jinja2 import Environment, FileSystemLoader, Template
from flask import url_for, request
from api import TEMPLATE_FOLDER_PATH

ENV = Environment(loader=FileSystemLoader('.'))


class ReportService:
    """Service for all template related operations"""

    @classmethod
    def create_report_from_stored_template(cls, template_name: str, template_args: object, report_name: str):
        template = ENV.get_template('{}/{}.html'.format(TEMPLATE_FOLDER_PATH, template_name))
        bc_logo_url = url_for('static', filename='images/bc_logo.png')
        registries_url = url_for('static', filename='images/reg_logo.png')
        html_out = template.render(template_args, bclogoUrl=bc_logo_url, registriesurl=registries_url)
        pdf_out = render_pdf(HTML(string=html_out, base_url=request.base_url), automatic_download=True, download_filename='{}.pdf'.format(report_name))
        return pdf_out

    @classmethod
    def create_report_from_template(cls, template_string: str, template_args: object, report_name: str):
        template_decoded = base64.b64decode(template_string).decode('utf-8')
        template_ = Template(template_decoded)
        html_out = template_.render(template_args)
        pdf_out = render_pdf(HTML(string=html_out, base_url=request.base_url), automatic_download=True, download_filename='{}.pdf'.format(report_name))
        return pdf_out
