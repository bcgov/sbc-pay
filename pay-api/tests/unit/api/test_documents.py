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

"""Tests to assure the documents end-point.

Test-Suite to ensure that the /documents endpoint is working as expected.
"""

import pytest

from pay_api.utils.enums import DocumentType
from pay_api.utils.errors import Error
from tests.utilities.base_test import get_claims, token_header


@pytest.mark.parametrize("document_type", [None, "ABC"])
def test_documents_invalid(session, client, jwt, app, document_type):
    """Assert that the endpoint returns 400 for invalid documents."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    document_url = "/api/v1/documents" if document_type is None else f"/api/v1/documents?documentType={document_type}"
    rv = client.get(document_url, headers=headers)
    assert rv.status_code == 400
    assert rv.json["type"] == Error.DOCUMENT_TYPE_INVALID.name


@pytest.mark.parametrize("document_type", [DocumentType.EFT_INSTRUCTIONS.value])
def test_documents(session, client, jwt, app, document_type):
    """Assert that the endpoint returns 200 for valid documents."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {"Authorization": f"Bearer {token}", "content-type": "application/json"}
    rv = client.get(f"/api/v1/documents?documentType={document_type}", headers=headers)
    assert rv.status_code == 200
