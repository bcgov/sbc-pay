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


"""Tests to assure the Template.

Test suite for reports
"""

import base64
import json

from .base_test import get_claims, token_header


def test_get_generate(client):
    """Status check."""
    rv = client.get('/api/v1/reports')
    assert rv.status_code == 200


def test_generate_report_with_existing_template(client, jwt, app):
    """Call to generate report with existing template."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.get('/api/v1/templates')
    template_name = rv.json['report-templates'][0]
    assert template_name is not None
    request_url = '/api/v1/reports'
    request_data = {
        'templateName': template_name,
        'templateVars': {
            'title': 'This is a sample request',
            'invoice': {}
        },
        'reportName': 'sample'
    }

    rv = client.post(request_url, data=json.dumps(request_data), headers=headers)
    assert rv.status_code == 200
    assert rv.content_type == 'application/pdf'


def test_generate_report_with_invalid_template(client, jwt, app):
    """Call to generate report with invalid template."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    request_url = '/api/v1/reports'
    request_data = {
        'templateName': 'some-really-random-values',
        'templateVars': {
            'title': 'This is a sample request'
        },
        'reportName': 'sample'
    }
    rv = client.post(request_url, data=json.dumps(request_data), headers=headers)
    assert rv.status_code == 404


def test_generate_report_with_template(client, jwt, app):
    """Call to generate report with new template."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    template = '<html><body><h1>Sample Report</h1><h2>{{ title }}</h2></body></html>'
    template = base64.b64encode(bytes(template, 'utf-8')).decode('utf-8')
    request_url = '/api/v1/reports'
    request_data = {
        'template': template,
        'templateVars': {
            'title': 'This is a sample request'
        },
        'reportName': 'Test Report'
    }
    rv = client.post(request_url, data=json.dumps(request_data), headers=headers)
    assert rv.status_code == 200
    assert rv.content_type == 'application/pdf'


def test_generate_report_with_page_number(client, jwt, app):
    """Call to generate report with new template."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    template = '<html><body><h1>Sample Report</h1><h2>{{ title }}</h2></body></html>'
    template = base64.b64encode(bytes(template, 'utf-8')).decode('utf-8')
    request_url = '/api/v1/reports'
    request_data = {
        'template': template,
        'templateVars': {
            'title': 'This is a sample request'
        },
        'reportName': 'Test Report',
        'populatePageNumber': 'true'
    }
    rv = client.post(request_url, data=json.dumps(request_data), headers=headers)
    assert rv.status_code == 200
    assert rv.content_type == 'application/pdf'


def test_generate_report_with_invalid_request(client, jwt, app):
    """Call to generate report with invalid request."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    request_url = '/api/v1/reports'
    request_data = {
        'templateVars': {
            'title': 'This is a sample request'
        },
        'reportName': 'Test Report'
    }
    rv = client.post(request_url, data=json.dumps(request_data), headers=headers)
    assert rv.status_code == 400


def test_csv_report(client, jwt, app):
    """Call to generate report with invalid request."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json',
        'Accept': 'text/csv'
    }
    request_url = '/api/v1/reports'
    request_data = {
        'reportName': 'test',
        'templateVars': {
            'columns': [
                'a',
                'b',
                'c'
            ],
            'values': [
                [
                    '1',
                    '2',
                    '3'
                ],
                [
                    '4',
                    '5',
                    '6'
                ]
            ]
        }
    }
    rv = client.post(request_url, data=json.dumps(request_data), headers=headers)
    assert rv.status_code == 200


def test_csv_report_with_invalid_request(client, jwt, app):
    """Call to generate report with invalid request."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json',
        'Accept': 'text/csv'
    }
    request_url = '/api/v1/reports'
    request_data = {
        'reportName': 'test',
        'templateVars': {

        }
    }
    rv = client.post(request_url, data=json.dumps(request_data), headers=headers)
    assert rv.status_code == 400
