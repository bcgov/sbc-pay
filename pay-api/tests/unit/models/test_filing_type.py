# Copyright © 2024 Province of British Columbia
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

"""Tests to assure the FilingType Class.

Test-Suite to ensure that the FilingType Class is working as expected.
"""

from pay_api.models import FilingType


def factory_filing_type(code: str, description: str):
    """Return a valid FilingType object."""
    return FilingType(code=code,
                      description=description)


def test_filing_type(session):
    """Assert a valid filing type is stored correctly.

    Start with a blank database.
    """
    filing_type = factory_filing_type('OTADDX', 'Annual Report')
    filing_type.save()

    assert filing_type.code is not None


def test_filing_type_find_by_code(session):
    """Assert that the filing type can be found by code."""
    filing_type = factory_filing_type('OTADDX', 'Annual Report')
    session.add(filing_type)
    session.commit()

    b = FilingType.find_by_code('OTADDX')
    assert b is not None


def test_filing_type_find_by_invalid_fee_code(session):
    """Assert that the filing type can not be found, with invalid code."""
    filing_type = factory_filing_type('OTADDX', 'Annual Report')
    session.add(filing_type)
    session.commit()

    b = FilingType.find_by_code('OTANNX')
    assert b is None
