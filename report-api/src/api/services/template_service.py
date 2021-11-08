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

import fnmatch
import os
import os.path

from jinja2 import Environment, FileSystemLoader

from api.utils.util import TEMPLATE_FOLDER_PATH


ENV = Environment(loader=FileSystemLoader('.'))


class TemplateService:
    """Service for all template related operations."""

    @staticmethod
    def find_all_templates():
        """Get all templates."""
        template_names = []
        list_of_files = os.listdir(TEMPLATE_FOLDER_PATH)
        for filename in list_of_files:
            if fnmatch.fnmatch(filename, '*.html'):
                template_names.append(os.path.splitext(filename)[0])
        return template_names

    @classmethod
    def get_stored_template(cls, templatename: str, ):
        """Get a stored template."""
        template = ENV.get_template(f'{TEMPLATE_FOLDER_PATH}/{templatename}.html')
        html_template = template.render()
        return html_template
