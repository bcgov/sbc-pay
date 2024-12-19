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

"""Tests to assure the Payment Method Service.

Test-Suite to ensure that the Payment Method Service is working as expected.
"""

from pay_api.services import PaymentMethodService
from tests.unit.models.test_products import factory_product


def test_find_payment_methods_with_product_code(session, clear_products_table):
    """Assert that payment methods are returned for a specific product code."""
    product = factory_product("PPR", ["PAD", "DIRECT_PAY"])
    session.add(product)
    session.commit()

    payment_methods = PaymentMethodService.find_payment_methods("PPR")
    assert payment_methods is not None
    assert payment_methods == {"PPR": ["PAD", "DIRECT_PAY"]}


def test_find_payment_methods_with_invalid_product_code(session, clear_products_table):
    """Assert that empty dict is returned for invalid product code."""
    product = factory_product("PPR", ["PAD", "DIRECT_PAY"])
    session.add(product)
    session.commit()

    payment_methods = PaymentMethodService.find_payment_methods("INVALID")
    assert payment_methods == {}


def test_find_all_payment_methods(session, clear_products_table):
    """Assert that payment methods are returned for all products."""
    product1 = factory_product("PPR", ["PAD", "DIRECT_PAY"])
    product2 = factory_product("BCA", ["PAD", "ONLINE_BANKING"])
    session.add(product1)
    session.add(product2)
    session.commit()

    payment_methods = PaymentMethodService.find_payment_methods()
    assert payment_methods is not None
    assert len(payment_methods) == 2
    assert payment_methods["PPR"] == ["PAD", "DIRECT_PAY"]
    assert payment_methods["BCA"] == ["PAD", "ONLINE_BANKING"]
