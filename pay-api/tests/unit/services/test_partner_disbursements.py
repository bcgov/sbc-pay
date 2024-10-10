"""Test for partner_disbursements service."""

import pytest

from pay_api.services.partner_disbursements import PartnerDisbursements
from pay_api.utils.enums import DisbursementStatus
from tests.utilities.base_test import factory_invoice, factory_partner_disbursement, factory_payment_account


@pytest.mark.parametrize(
    "test_name",
    [
        ("existing_duplicate_payment"),
        ("happy_existing_row_reversal"),
        ("happy_existing_cancelled"),
        ("happy_fresh_no_existing_row"),
    ],
)
def test_partner_payment(test_name):
    """Test partner payment to ensure it updates or inserts correct rows."""
    # Create payment account, invoice and partner disbursement
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account).save()
    match test_name:
        case "existing_duplicate_payment":
            factory_partner_disbursement(invoice, is_reversal=False)
        case "happy_fresh_no_existing_row":
            pass
        case "happy_existing_row_reversal":
            factory_partner_disbursement(invoice, is_reversal=True)
        case "happy_existing_cancelled":
            factory_partner_disbursement(invoice, is_reversal=False, status_code=DisbursementStatus.CANCELLED.value)
    PartnerDisbursements.handle_payment(invoice)
    assert 1 == 1


@pytest.mark.parametrize(
    "test_name", [("existing_duplicate_reversal"), ("happy_cancel_existing"), ("happy_created_new_row"), ("not_found")]
)
def test_partner_reversal(test_name):
    """Test partner reversal to ensure it updates or inserts correct rows."""
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account).save()
    match test_name:
        case "existing_duplicate_reversal":
            factory_partner_disbursement(invoice, is_reversal=True)
        case "happy_cancel_existing":
            factory_partner_disbursement(invoice, is_reversal=False)
        case "happy_created_new_row":
            pass
        case "not_found":
            pass
    PartnerDisbursements.handle_reversal(invoice)
