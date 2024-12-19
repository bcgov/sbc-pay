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
"""Tests to assure the products end-point.

Test-Suite to ensure that the /products endpoint is working as expected.
"""

from http import HTTPStatus

from tests.utilities.base_test import get_claims, token_header


def test_get_valid_payment_methods(session, client, jwt, app):
    """Assert that the endpoint returns valid payment methods for a product."""
    rv = client.get("/api/v1/products/valid_payment_methods/BUSINESS")

    assert rv.status_code == HTTPStatus.OK
    assert rv.json is not None
