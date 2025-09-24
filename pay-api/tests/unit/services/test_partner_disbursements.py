"""Test for partner_disbursements service."""

import pytest

from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PartnerDisbursements as PartnerDisbursementsModel
from pay_api.models import RefundsPartial as RefundsPartialModel
from pay_api.services.partner_disbursements import PartnerDisbursements
from pay_api.utils.enums import DisbursementStatus, EJVLinkType
from tests.utilities.base_test import (
    factory_invoice,
    factory_partner_disbursement,
    factory_payment_account,
    factory_payment_line_item,
)


def setup_data() -> InvoiceModel:
    """Get THAT data setup."""
    payment_account = factory_payment_account()
    invoice = factory_invoice(payment_account, total=8.5, service_fees=1.5).save()
    corp_type = CorpTypeModel.find_by_code("CP")
    corp_type.has_partner_disbursements = True
    corp_type.save()
    return invoice


@pytest.mark.parametrize(
    "test_name, assertion_count",
    [
        ("bad_invoice_amount", 0),
        ("existing_duplicate_payment", 1),
        ("happy_existing_row_reversal", 2),
        ("happy_existing_cancelled", 2),
        ("happy_fresh_no_existing_row", 1),
    ],
)
def test_partner_payment(session, test_name, assertion_count):
    """Test partner payment to ensure it updates or inserts correct rows."""
    # Create payment account, invoice and partner disbursement
    invoice = setup_data()
    match test_name:
        case "bad_invoice_amount":
            invoice.total = 0
            invoice.save()
        case "existing_duplicate_payment":
            factory_partner_disbursement(invoice, is_reversal=False)
        case "happy_fresh_no_existing_row":
            pass
        case "happy_existing_row_reversal":
            factory_partner_disbursement(invoice, is_reversal=True)
        case "happy_existing_cancelled":
            factory_partner_disbursement(invoice, is_reversal=False, status_code=DisbursementStatus.CANCELLED.value)
    PartnerDisbursements.handle_payment(invoice)
    assert assertion_count == PartnerDisbursementsModel.query.count()
    if test_name.startswith("happy"):
        assert (
            PartnerDisbursementsModel.query.filter_by(is_reversal=False)
            .filter_by(status_code=DisbursementStatus.WAITING_FOR_JOB.value)
            .order_by(PartnerDisbursementsModel.id.desc())
            .first()
            .amount
            == 7.0
        )


@pytest.mark.parametrize(
    "test_name, assertion_count",
    [("existing_duplicate_reversal", 1), ("happy_cancel_existing", 1), ("happy_created_new_row", 2), ("not_found", 0)],
)
def test_partner_reversal(session, test_name, assertion_count):
    """Test partner reversal to ensure it updates or inserts correct rows."""
    invoice = setup_data()
    match test_name:
        case "existing_duplicate_reversal":
            factory_partner_disbursement(invoice, is_reversal=True)
        case "happy_cancel_existing":
            factory_partner_disbursement(
                invoice, is_reversal=False, status_code=DisbursementStatus.WAITING_FOR_JOB.value
            )
        case "happy_created_new_row":
            factory_partner_disbursement(invoice, is_reversal=False, status_code=DisbursementStatus.COMPLETED.value)
        case "not_found":
            pass
    PartnerDisbursements.handle_reversal(invoice)
    assert assertion_count == PartnerDisbursementsModel.query.count()
    match test_name:
        case "happy_cancel_existing":
            assert (
                PartnerDisbursementsModel.query.filter_by(is_reversal=False)
                .filter_by(status_code=DisbursementStatus.CANCELLED.value)
                .order_by(PartnerDisbursementsModel.id.desc())
                .first()
            )

        case "happy_create_new_row":
            assert (
                PartnerDisbursementsModel.query.filter_by(is_reversal=True)
                .filter_by(status_code=DisbursementStatus.WAITING_FOR_JOB.value)
                .order_by(PartnerDisbursementsModel.id.desc())
                .first()
                .amount
                == 7.0
            )


def factory_refunds_partial(invoice, payment_line_item_id, refund_amount=10.0, refund_type="BASE_FEES"):
    """Return refunds partial model."""
    return RefundsPartialModel(
        invoice_id=invoice.id,
        payment_line_item_id=payment_line_item_id,
        refund_amount=refund_amount,
        refund_type=refund_type,
        created_by="test_user",
    ).flush()


@pytest.mark.parametrize(
    "test_name, should_skip, has_existing_disbursement, expected_count",
    [
        ("skip_partner_disbursement", True, False, 0),
        ("create_new_disbursement", False, False, 1),
        ("existing_disbursement", False, True, 1),
    ],
)
def test_handle_partial_refund(session, test_name, should_skip, has_existing_disbursement, expected_count, monkeypatch):
    """Test partner partial refund to ensure it creates disbursement rows as expected."""
    invoice = setup_data()

    payment_line_item = factory_payment_line_item(invoice.id, 1, filing_fees=10, total=10)
    payment_line_item = payment_line_item.save()

    partial_refund = factory_refunds_partial(invoice, payment_line_item.id, refund_amount=5.0)

    if should_skip:
        monkeypatch.setattr(PartnerDisbursements, "_skip_partner_disbursement", lambda *args: True)  # noqa: ARG005

    if has_existing_disbursement:
        PartnerDisbursementsModel(
            amount=partial_refund.refund_amount,
            is_reversal=True,
            partner_code=invoice.corp_type_code,
            status_code=DisbursementStatus.WAITING_FOR_JOB.value,
            target_id=partial_refund.id,
            target_type=EJVLinkType.PARTIAL_REFUND.value,
        ).flush()

    PartnerDisbursements.handle_partial_refund(partial_refund, invoice)

    disbursements = PartnerDisbursementsModel.query.filter_by(
        target_id=partial_refund.id, target_type=EJVLinkType.PARTIAL_REFUND.value
    ).all()

    assert len(disbursements) == expected_count

    if not should_skip and not has_existing_disbursement:
        assert disbursements[0].amount == partial_refund.refund_amount
        assert disbursements[0].is_reversal is True
        assert disbursements[0].partner_code == invoice.corp_type_code
        assert disbursements[0].status_code == DisbursementStatus.WAITING_FOR_JOB.value
        assert disbursements[0].target_type == EJVLinkType.PARTIAL_REFUND.value
