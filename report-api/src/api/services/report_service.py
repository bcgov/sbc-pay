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

"""Service to  manage report-templates."""

import base64

from flask import url_for
from jinja2 import Environment, FileSystemLoader, Template
from weasyprint import HTML
from weasyprint.formatting_structure.boxes import InlineBox

from api.utils.constants import JINJA_AUTO_ESCAPE
from api.utils.util import TEMPLATE_FOLDER_PATH


ENV = Environment(loader=FileSystemLoader('.'), autoescape=JINJA_AUTO_ESCAPE)


class ReportService:
    """Service for all template related operations."""

    @classmethod
    def create_report_from_stored_template(cls, template_name: str, template_args: object,
                                           generate_page_number: bool = False):
        """Create a report from a stored template."""
        template = ENV.get_template('{}/{}.html'.format(TEMPLATE_FOLDER_PATH, template_name))
        bc_logo_url = url_for('static', filename='images/bcgov-logo-vert.jpg')
        registries_url = url_for('static', filename='images/reg_logo.png')
        html_out = template.render(template_args, bclogoUrl=bc_logo_url, registriesurl=registries_url)
        return ReportService.generate_pdf(html_out, generate_page_number)

    @classmethod
    def create_report_from_template(cls, template_string: str, template_args: object,
                                    generate_page_number: bool = False):
        """Create a report from a json template."""
        template_decoded = base64.b64decode(template_string).decode('utf-8')
        template_ = Template(template_decoded, autoescape=JINJA_AUTO_ESCAPE)
        html_out = template_.render(template_args)
        return ReportService.generate_pdf(html_out, generate_page_number)

    @staticmethod
    def generate_pdf(html_out, generate_page_number: bool = False):
        """Generate pdf out of the html."""
        html = HTML(string=html_out).render()
        if generate_page_number:
            html = ReportService.populate_page_info(html)

        return html.write_pdf()

    @staticmethod
    def populate_page_info(html):
        """Iterate through pages and populate page number info."""
        total_pages = len(html.pages)
        count = 1
        for page in html.pages:
            ReportService.populate_page_count(page._page_box, count, total_pages)  # pylint: disable=protected-access
            count = count + 1
        return html

    @staticmethod
    def populate_page_count(box, count, total):
        """Iterate through boxes and populate page info under pageinfo tag."""
        if box.element_tag:
            if box.element_tag == 'pageinfo':
                page_info_text = f'Page {count} of {total}'
                if isinstance(box, InlineBox):
                    box.children[0].text = page_info_text
                    box.children[0].pango_layout.text = page_info_text
                box.text = page_info_text
        if box.all_children():
            for b in box.children:
                ReportService.populate_page_count(b, count, total)
