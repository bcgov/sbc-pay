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

"""Tests to assure the CorpType Class.

Test-Suite to ensure that the CorpType Class is working as expected.
"""

# from pay_api.models.status_code import StatusCode


# def factory_status_code(code: str = 'DRAFT', description='Draft'):
#     """Factory."""
#     return StatusCode(code=code, description=description)
#
#
# def test_status_code(session):
#     """Assert a status_code is stored.
#
#     Start with a blank database.
#     """
#     status_code = factory_status_code(code='XX', description='TEST')
#     status_code.save()
#     assert status_code.code == 'XX'
