# Copyright © 2022 Province of British Columbia
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

"""Tests to assure the PAYBC service layer.

Test-Suite to ensure that the PAYBC layer is working as expected.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

from dateutil import parser

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.services.paybc_service import PaybcService
from tests.utilities.base_test import factory_invoice, factory_invoice_reference, factory_payment_account

paybc_service = PaybcService()


def test_create_account(session):
    """Test create_account."""
    account = paybc_service.create_account(identifier="100", contact_info={}, payment_info={})
    assert account
    assert account.cfs_account
    assert account.cfs_party
    assert account.cfs_site


def test_get_payment_system_url_for_invoice(session):
    """Test get_payment_system_code."""
    payment_account = factory_payment_account().save()
    invoice = factory_invoice(payment_account).save()
    invoice_reference = factory_invoice_reference(invoice.id, invoice_number="100")
    payment_system_url = paybc_service.get_payment_system_url_for_invoice(invoice, invoice_reference, "hello")
    assert payment_system_url
    assert "inv_number=100" in payment_system_url
    assert "redirect_uri=hello" in payment_system_url
    assert "pbc_ref_number" in payment_system_url


@patch("pay_api.services.paybc_service.CFSService.get_token")
def test_get_receipt_no_receipt_number(mock_get_token, session):
    """Test get_receipt when no receipt_number is provided in pay_response_url."""
    mock_token_response = MagicMock()
    mock_token_response.json.return_value = {"access_token": "test_token"}
    mock_get_token.return_value = mock_token_response

    payment_account = factory_payment_account()
    payment_account.cfs_party = "123"
    payment_account.cfs_account = "456"
    payment_account.cfs_site = "789"

    cfs_account = CfsAccountModel()
    cfs_account.save()

    invoice = factory_invoice(payment_account, cfs_account_id=cfs_account.id).save()
    invoice_reference = factory_invoice_reference(invoice.id, invoice_number="INV-001")
    pay_response_url = "https://test.com/pay?status=success"

    with (
        patch.object(
            paybc_service,
            "get_invoice",
            return_value={
                "receipts": [
                    {
                        "links": [
                            {
                                "rel": "receipt_applied",
                                "href": "https://ggogo/cfs/rcpts/PYBCCC052435_01964218/",
                            }
                        ]
                    }
                ]
            },
        ),
        patch.object(
            paybc_service,
            "_get_receipt_by_number",
            return_value={
                "receipt_date": "2024-01-15T10:30:00Z",
                "receipt_number": "PYBCCC052435_01964218",
                "amount_applied": "100.00",
            },
        ),
    ):

        result = paybc_service.get_receipt(payment_account, pay_response_url, invoice_reference)

        assert result is not None
        assert result[0] == "PYBCCC052435_01964218"
        assert isinstance(result[1], datetime)
        assert result[2] == 100.0
        mock_get_token.assert_called_once()
