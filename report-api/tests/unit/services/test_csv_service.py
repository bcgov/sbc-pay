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


"""Tests to assure the CSV  Service.

Test suite for template service
"""

from api.services import CsvService


def test_create_csv(app):
    """Test create csv."""
    csv_payload = {
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
    csv_report = CsvService.create_report(csv_payload)
    assert csv_report is not None


def test_create_csv_with_no_data(app):
    """Test create csv."""
    csv_payload = {
    }
    csv_report = CsvService.create_report(csv_payload)
    assert csv_report is None
