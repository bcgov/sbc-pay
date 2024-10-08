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

from pay_api.services.paybc_service import PaybcService
from tests.utilities.base_test import (
    factory_invoice,
    factory_invoice_reference,
    factory_payment_account,
)

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
