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

import csv
from tempfile import NamedTemporaryFile
from typing import Dict


class CsvService:  # pylint: disable=too-few-public-methods
    """Service for all template related operations."""

    @classmethod
    def create_report(cls, payload: Dict):
        """Create a report csv report from the input parameters."""
        temp_file = None
        columns = payload.get('columns', None)
        values = payload.get('values', None)
        if columns:
            temp_file = NamedTemporaryFile(delete=True)  # pylint: disable=consider-using-with
            with open(temp_file.name, 'w', newline='', encoding='utf-8') as csvfile:
                report = csv.writer(csvfile)
                report.writerow(columns)
                for row in values:
                    report.writerow(row)

        return temp_file
