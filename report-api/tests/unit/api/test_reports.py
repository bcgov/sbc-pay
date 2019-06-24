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


def test_get_generate(client):
    """Status check."""
    rv = client.get('/api/v1/reports')
    assert rv.status_code == 200


def test_generate_report_with_existing_template(client):
    """Call to generate report with existing template."""
    rv = client.get('/api/v1/templates')
    print(rv.json)
    template_name = rv.json['report-templates'][0]
    assert template_name is not None
    request_url = '/api/v1/reports'.format(template_name)
    request_data = {
        'template_name': template_name,
        'template_vars': {
            'title': 'This is a sample request'
        },
        'report_name': 'sample'
    }

    rv = client.post(request_url, data=json.dumps(request_data), content_type='application/json')
    assert rv.status_code == 200
    assert rv.content_type == 'application/pdf'


def test_generate_report_with_invalid_template(client):
    """Call to generate report with invalid template."""
    template_name = 'some-random-text-to-fial-generation'
    request_url = '/api/v1/reports'.format(template_name)
    request_data = {
        'template_name': 'some-really-random-values',
        'template_vars': {
            'title': 'This is a sample request'
        },
        'report_name': 'sample'
    }
    rv = client.post(request_url, data=json.dumps(request_data), content_type='application/json')
    assert rv.status_code == 404


def test_generate_report_with_template(client):
    """Call to generate report with new template."""
    template = '<html><body><h1>Sample Report</h1><h2>{{ title }}</h2></body></html>'
    template = base64.b64encode(bytes(template, 'utf-8')).decode('utf-8')
    request_url = '/api/v1/reports'
    request_data = {
        'template': template,
        'template_vars': {
            'title': 'This is a sample request'
        },
        'report_name': 'Test Report'
    }
    rv = client.post(request_url, data=json.dumps(request_data), content_type='application/json')
    assert rv.status_code == 200
    assert rv.content_type == 'application/pdf'


def test_generate_report_with_invalid_request(client):
    """Call to generate report with invalid request."""
    request_url = '/api/v1/reports'
    request_data = {
        'template_vars': {
            'title': 'This is a sample request'
        },
        'report_name': 'Test Report'
    }
    rv = client.post(request_url, data=json.dumps(request_data), content_type='application/json')
    assert rv.status_code == 400
