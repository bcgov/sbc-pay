# Copyright © 2024 Province of British Columbia
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
"""Service to manage payment methods validation."""

from pay_api.models import Product as ProductModel


class PaymentMethodService:
    """Service to manage payment methods."""

    @classmethod
    def find_payment_methods(cls, product_code: str | None = None) -> dict:
        """Find payment methods for a product."""
        if not product_code:
            products = ProductModel.query.all()
            payment_methods_by_product = {}
            for product in products:
                payment_methods_by_product[product.product_code] = product.payment_methods
            return payment_methods_by_product

        product = ProductModel.query.filter_by(product_code=product_code).first()
        if product:
            return {product.product_code: product.payment_methods}
        return {}
