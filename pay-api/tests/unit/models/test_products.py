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

"""Tests to assure the Product Class.

Test-Suite to ensure that the Product Class is working as expected.
"""
from pay_api.models import Product


def factory_product(product_code: str, payment_methods: list):
    """Return a valid Product object."""
    return Product(product_code=product_code, payment_methods=payment_methods)


def test_product(session, clear_products_table):
    """Assert a valid product is stored correctly.

    Start with a blank database.
    """
    product = factory_product("PPR", ["PAD", "DIRECT_PAY"])
    product.save()

    assert product.product_code is not None


def test_product_find_by_code(session, clear_products_table):
    """Assert that the product can be found by code."""
    product = factory_product("PPR", ["PAD", "DIRECT_PAY"])
    session.add(product)
    session.commit()

    p = Product.query.filter_by(product_code="PPR").one_or_none()
    assert p is not None
    assert p.product_code == "PPR"
    assert p.payment_methods == ["PAD", "DIRECT_PAY"]


def test_product_find_by_invalid_code(session, clear_products_table):
    """Assert that the product can not be found, with invalid code."""
    product = factory_product("PPR", ["PAD", "DIRECT_PAY"])
    session.add(product)
    session.commit()

    p = Product.query.filter_by(product_code="INVALID").one_or_none()
    assert p is None
