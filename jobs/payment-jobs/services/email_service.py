# Copyright © 2024 Province of British Columbia
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

"""This manages all of the email notification service."""

import os

from flask import current_app
from jinja2 import Environment, FileSystemLoader


def _get_template(template_file_name: str):
    """Retrieve template."""
    # Refactor this common code to PAY-API.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(current_dir)
    templates_dir = os.path.join(project_root_dir, "templates")
    env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)
    return env.get_template(template_file_name)


def _render_eft_overpayment_template(params: dict) -> str:
    """Render eft overpayment template."""
    template = _get_template("eft_overpayment.html")
    short_name_detail_url = f"{current_app.config.get('PAY_WEB_URL')}/eft/shortname-details/{params['shortNameId']}"
    params["shortNameDetailUrl"] = short_name_detail_url

    return template.render(params)
