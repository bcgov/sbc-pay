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
"""EFT reconciliation file."""
import dataclasses
import json
import os
from typing import Any, Dict, List, Optional

from flask import current_app
from jinja2 import Environment, FileSystemLoader
from pay_api.services.email_service import send_email as send_email_service

from pay_queue.auth import get_token


@dataclasses.dataclass
class EmailParams:
    """Params required to send error email."""

    subject: Optional[str] = ''
    file_name: Optional[str] = None
    minio_location: Optional[str] = None
    error_messages: Optional[List[Dict[str, Any]]] = dataclasses.field(default_factory=list)
    ce: Optional[Any] = None
    table_name: Optional[str] = None


def send_error_email(params: EmailParams):
    """Send the email asynchronously, using the given details."""
    recipient = current_app.config.get('IT_OPS_EMAIL')
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(current_dir)
    templates_dir = os.path.join(project_root_dir, 'templates')
    env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)

    template = env.get_template('payment_reconciliation_failed_email.html')

    email_params = {
        'fileName': params.file_name,
        'errorMessages': params.error_messages,
        'minioLocation': params.minio_location,
        'payload': json.dumps(dataclasses.asdict(params.ce)),
        'tableName': params.table_name
    }

    html_body = template.render(email_params)

    token = get_token()
    send_email_service(
        recipients=[recipient],
        subject=params.subject,
        html_body=html_body,
        user=type('User', (), {'bearer_token': token})()
    )
