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

"""Tests to assure the Code Service.

Test-Suite to ensure that the Code Service is working as expected.
"""

from pay_api.services.code import Code as CodeService
from pay_api.utils.cache import cache
from pay_api.utils.enums import Code


def test_build_cache(session):
    """Assert that code cache is built."""
    CodeService.build_all_codes_cache()
    assert cache is not None
    assert cache.get(Code.ERROR.value) is not None


def test_find_code_values_by_type(session):
    """Assert that code values are returned."""
    codes = CodeService.find_code_values_by_type(Code.ERROR.value)
    assert codes is not None
    assert len(codes) > 0


def test_find_code_value_by_type_and_code(session):
    """Assert that code values are returned."""
    codes = CodeService.find_code_values_by_type(Code.ERROR.value)
    first_code = codes.get('codes')[0].get('type')
    cache.clear()
    code = CodeService.find_code_value_by_type_and_code(Code.ERROR.value, first_code)
    assert code is not None
    assert code.get('type') == first_code

    codes = CodeService.find_code_values_by_type(Code.INVOICE_STATUS.value)
    first_code = codes.get('codes')[0].get('type')
    cache.clear()
    code = CodeService.find_code_value_by_type_and_code(Code.INVOICE_STATUS.value, first_code)
    assert code is not None
    assert code.get('type') == first_code


def test_find_payment_types_code_values(session):
    """Assert that code values are returned."""
    codes = CodeService.find_code_values_by_type(Code.INVOICE_STATUS.value)
    assert codes is not None
    assert len(codes) > 0
