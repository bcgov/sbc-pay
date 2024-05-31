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

"""Tests to assure the error utilities.

Test-Suite to ensure that the error is working as expected.
"""

from pay_api.utils.errors import Error, get_bcol_error


def test_get_bcol_error(capsys):
    """Assert get_bcol_error."""
    assert get_bcol_error(1) == Error.BCOL_ERROR
    assert get_bcol_error(7) == Error.BCOL_UNAVAILABLE
    assert get_bcol_error(20) == Error.BCOL_ACCOUNT_CLOSED
    assert get_bcol_error(21) == Error.BCOL_USER_REVOKED
    assert get_bcol_error(48) == Error.BCOL_ACCOUNT_REVOKED
    assert get_bcol_error(61) == Error.BCOL_ACCOUNT_INSUFFICIENT_FUNDS
