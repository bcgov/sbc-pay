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

"""Tests to assure the CorpType Class.

Test-Suite to ensure that the CorpType Class is working as expected.
"""

from pay_api.models import CorpType


def factory_corp_type(corp_type_code: str, corp_description: str, product: str = None, payment_methods: list = None):
    """Return a valid Corp Type object."""
    corp_type = CorpType(code=corp_type_code, description=corp_description)
    if product:
        corp_type.product = product
    if payment_methods:
        corp_type.payment_methods = payment_methods
    return corp_type


def test_corp_type(session):
    """Assert a valid corp type is stored correctly.

    Start with a blank database.
    """
    corp_type = factory_corp_type("XX", "Cooperative")
    corp_type.save()

    assert corp_type.code is not None


def test_corp_type_by_code(session):
    """Assert that the corp type can be found by code."""
    corp_type = factory_corp_type("XX", "Cooperative")
    session.add(corp_type)
    session.commit()

    b = CorpType.find_by_code("XX")
    assert b is not None


def test_corp_type_by_invalid_code(session):
    """Assert that the corp type can not be found, with invalid code."""
    corp_type = factory_corp_type("XX", "Cooperative")
    session.add(corp_type)
    session.commit()

    b = CorpType.find_by_code("AB")
    assert b is None


def test_payment_methods(session):
    """Assert that payment methods are stored and retrieved correctly."""
    business_corp = factory_corp_type(
        "XX", "Business", product="BUSINESS", payment_methods=["PAD", "DIRECT_PAY", "ONLINE_BANKING", "DRAWDOWN"]
    )
    session.add(business_corp)
    session.commit()

    retrieved_corp = CorpType.find_by_code("XX")
    assert retrieved_corp is not None
    assert retrieved_corp.payment_methods == ["PAD", "DIRECT_PAY", "ONLINE_BANKING", "DRAWDOWN"]
