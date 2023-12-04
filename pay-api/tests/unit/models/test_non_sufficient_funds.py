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

"""Tests to assure the Non-Sufficient Funds Class.

Test-Suite to ensure that the Non-Sufficient Funds Class is working as expected.
"""

from pay_api.models import NonSufficientFundsModel


def test_non_sufficient_funds(session):
    """Assert Non-Sufficient Funds defaults are stored."""
    non_sufficient_funds = NonSufficientFundsModel()
    non_sufficient_funds.invoice_id = 1
    non_sufficient_funds.description = 'NSF'
    non_sufficient_funds.save()

    assert non_sufficient_funds.id is not None
    assert non_sufficient_funds.invoice_id is not None
    assert non_sufficient_funds.description is not None
    