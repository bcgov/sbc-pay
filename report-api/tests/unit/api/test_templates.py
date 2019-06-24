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

Test suite for template
"""


def test_get_all_templates(client):
    """Status code check."""
    rv = client.get('/api/v1/templates')
    assert b'"payment_receipt_v1"' in rv.data
    assert 'payment_receipt_v1' in rv.json['report-templates']
    assert 'payment_receipt_v2' in rv.json['report-templates']
    assert rv.status_code == 200


def test_get_two_templates(client):
    """Call to generate report with 200."""
    rv = client.get('/api/v1/templates?name=payment_receipt_v2')
    assert rv.status_code == 200


def test_get_one_templates(client):
    """Donotexist template."""
    rv = client.get('/api/v1/templates?name=donotexist')
    assert rv.status_code == 404
