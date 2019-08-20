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


"""Tests to assure the Template Service  Service.

Test suite for template service
"""


from unittest.mock import patch

from api.services import TemplateService


def test_find_all_templates_by_three_templates(app):
    """Test create account."""
    with app.app_context():
        with patch('os.listdir') as mock_list_of_files:
            mock_list_of_files.return_value = ['payment_receipt.html', 'payment_bill.html', 'payment_signed.html']
            templates = TemplateService.find_all_templates()
            assert len(templates) == 3
            assert templates[0] == 'payment_receipt'
            assert templates[1] == 'payment_bill'
            assert templates[2] == 'payment_signed'


def test_find_all_templates_by_non_html_templates(app):
    """Test create account."""
    with app.app_context():
        with patch('os.listdir') as mock_list_of_files:
            mock_list_of_files.return_value = ['payment_receipt.word', 'payment_bill.html', 'payment_signed.html']
            templates = TemplateService.find_all_templates()
            assert len(templates) == 2
            assert templates[0] == 'payment_bill'
            assert templates[1] == 'payment_signed'


def test_find_all_templates_by_no_templates(app):
    """Test create account."""
    with app.app_context():
        with patch('os.listdir') as mock_list_of_files:
            mock_list_of_files.return_value = []
            templates = TemplateService.find_all_templates()
            print(templates)
            assert len(templates) == 0
