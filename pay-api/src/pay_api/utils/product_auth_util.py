# Copyright © 2025 Province of British Columbia
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
"""Utility for product authorizations helpers."""

from pay_api.utils.enums import Role
from pay_api.utils.user_context import UserContext, user_context


class ProductAuthUtil:
    """Utility class for product authorizations helpers."""

    @staticmethod
    @user_context
    def check_products_from_role_pattern(role_pattern: str, all_products_role: str, **kwargs) -> tuple:
        """Check roles to see if product filtering is applicable and return allowed products list."""
        user: UserContext = kwargs["user"]
        roles = user.roles or []
        has_all_products_role = all_products_role in roles
        if has_all_products_role:
            return None, False

        filter_by_product = Role.PRODUCT_REFUND_VIEWER.value in roles
        products = [s[: -len(role_pattern)].upper() for s in roles if s.endswith(role_pattern)]
        return products, filter_by_product
