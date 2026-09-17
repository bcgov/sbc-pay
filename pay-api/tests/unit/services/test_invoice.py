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

"""Tests to assure the FeeSchedule Service.

Test-Suite to ensure that the FeeSchedule Service is working as expected.
"""

from unittest.mock import patch

import pytest

from pay_api.exceptions import BusinessException
from pay_api.models import FeeSchedule
from pay_api.services.invoice import Invoice as Invoice_service
from pay_api.utils.constants import ALL_ALLOWED_ROLES
from pay_api.utils.enums import InvoiceStatus, PaymentMethod
from tests.utilities.base_test import (
    factory_invoice,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
)


def test_invoice_eft_created_return_completed(session):
    """Assert that the invoice is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    i = factory_invoice(
        status_code=InvoiceStatus.APPROVED.value,
        payment_account=payment_account,
        payment_method_code=PaymentMethod.EFT.value,
    )
    i.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(i.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    invoice = Invoice_service.find_by_id(i.id, skip_auth_check=True).asdict()

    assert invoice is not None
    assert invoice["payment_method"] == PaymentMethod.EFT.value
    assert invoice["status_code"] == InvoiceStatus.APPROVED.value


def test_invoice_saved_from_new(session):
    """Assert that the invoice is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    i = factory_invoice(payment_account=payment_account)
    i.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(i.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    invoice = Invoice_service.find_by_id(i.id, skip_auth_check=True)

    assert invoice is not None
    assert invoice.id is not None
    assert invoice.invoice_status_code is not None
    assert invoice.refund is None
    assert invoice.payment_date is None
    assert invoice.total is not None
    assert invoice.paid is not None
    assert invoice.payment_line_items is not None
    assert invoice.folio_number is not None
    assert invoice.business_identifier is not None


def test_invoice_invalid_lookup(session):
    """Test invalid lookup."""
    with pytest.raises(BusinessException) as excinfo:
        Invoice_service.find_by_id(999, skip_auth_check=True)
    assert excinfo.type == BusinessException


def test_invoice_find_by_id(session):
    """Assert that the invoice is saved to the table."""
    payment_account = factory_payment_account()
    payment_account.save()
    i = factory_invoice(payment_account=payment_account)
    i.save()

    invoice = Invoice_service.find_by_id(i.id, skip_auth_check=True)

    assert invoice is not None
    assert invoice.id is not None
    assert invoice.invoice_status_code is not None
    assert invoice.refund is None
    assert invoice.payment_date is None
    assert invoice.total is not None
    assert invoice.paid is not None
    assert not invoice.payment_line_items


def test_invoice_with_temproary_business_identifier(session):
    """Assert that the invoice dictionary is not include temproary business identifier."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    i = factory_invoice(payment_account=payment_account, business_identifier="Tzxcasd")
    i.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(i.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    invoice = Invoice_service.find_by_id(i.id, skip_auth_check=True)
    assert invoice is not None
    assert invoice.id is not None
    assert invoice.invoice_status_code is not None
    assert invoice.refund is None
    assert invoice.payment_date is None
    assert invoice.total is not None
    assert invoice.paid is not None
    assert invoice.payment_line_items is not None
    assert invoice.folio_number is not None
    assert invoice.business_identifier is not None
    invoice_dict = invoice.asdict()
    assert invoice_dict.get("business_identifier") is None


@pytest.mark.parametrize(
    "allow_linking_key,has_linking_key,business_identifier,expected_account_id",
    [
        (True, True, "CP0001234", None),  # linking-key branch: no account_id
        (False, True, "CP0001234", "VENDOR_777"),  # linking-key not allowed, use account id only
        (True, True, None, "VENDOR_777"),  # no business_identifier - account id only
        (True, False, "CP0001234", "VENDOR_777"),  # no linking key present - use account
    ],
)
def test_check_for_auth_linking_key(
    session, monkeypatch, allow_linking_key, has_linking_key, business_identifier, expected_account_id
):
    """Assert _check_for_auth only takes the linking-key/business-identifier branch when explicitly allowed."""
    payment_account = factory_payment_account(auth_account_id="VENDOR_777")
    payment_account.save()
    invoice_dao = factory_invoice(payment_account=payment_account, business_identifier=business_identifier)
    invoice_dao.save()

    monkeypatch.setattr(
        "pay_api.utils.user_context.get_account_linking_key",
        lambda: "test-linking-key" if has_linking_key else None,
    )

    with patch("pay_api.services.invoice.check_auth", return_value={"roles": []}) as mock_check_auth:
        Invoice_service._check_for_auth(invoice_dao, allow_linking_key=allow_linking_key)  # pylint: disable=protected-access

    mock_check_auth.assert_called_once()
    called_args, called_kwargs = mock_check_auth.call_args
    assert called_args[0] == business_identifier
    assert called_kwargs.get("account_id") == expected_account_id
    assert called_kwargs.get("one_of_roles") == ALL_ALLOWED_ROLES
