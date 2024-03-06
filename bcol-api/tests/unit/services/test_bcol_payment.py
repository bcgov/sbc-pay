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

"""Tests to assure the BCOL payment servcie layer.

Test-Suite to ensure that the BCOL Service layer is working as expected.
"""

import unittest
from bcol_api.services.bcol_payment import BcolPayment


def test_payment(app, payment_mock):
    """Test payment service."""
    test_case = unittest.TestCase()
    with app.app_context():
        with test_case.assertLogs(level='ERROR') as log:
            payment_response = BcolPayment().create_payment({}, False)
            assert payment_response.get('userId') == 'PB25020'
            # Non matching fee case.
            BcolPayment().create_payment({'serviceFees': 50.00}, False)
            has_non_match_error = False
            for message in log.output:
                if "from BCOL doesn\'t match" in message:
                    has_non_match_error = True
            assert has_non_match_error
        # Success case.
        with test_case.assertNoLogs(level='ERROR'):
            BcolPayment().create_payment({'serviceFees': 1.50}, False)
