# Copyright © 2019 Province of British Columbia
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

"""Tests to assure the CreateAccountTask.

Test-Suite to ensure that the CreateAccountTask for routing slip is working as expected.
"""

from unittest.mock import MagicMock, patch

import pytest

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.services import CFSService
from pay_api.utils.enums import (
    CfsAccountStatus,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    ReverseOperation,
    RoutingSlipStatus,
)
from tasks.routing_slip_task import RoutingSlipTask

from .factory import (
    factory_distribution,
    factory_distribution_link,
    factory_invoice,
    factory_invoice_reference,
    factory_payment_line_item,
    factory_receipt,
    factory_routing_slip_account,
)


def test_link_rs(session):
    """Test link routing slip."""
    child_rs_number = "1234"
    parent_rs_number = "89799"
    factory_routing_slip_account(number=child_rs_number, status=CfsAccountStatus.ACTIVE.value)
    factory_routing_slip_account(number=parent_rs_number, status=CfsAccountStatus.ACTIVE.value)
    child_rs = RoutingSlipModel.find_by_number(child_rs_number)
    parent_rs = RoutingSlipModel.find_by_number(parent_rs_number)
    # Do Link
    child_rs.status = RoutingSlipStatus.LINKED.value
    child_rs.parent_number = parent_rs.number
    child_rs.save()
    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(child_rs.payment_account_id)

    cfs_account = CfsAccountModel.find_effective_by_payment_method(payment_account.id, PaymentMethod.INTERNAL.value)

    with patch("pay_api.services.CFSService.reverse_rs_receipt_in_cfs") as mock_cfs_reverse:
        with patch("pay_api.services.CFSService.create_cfs_receipt") as mock_create_cfs:
            with patch.object(CFSService, "get_receipt") as mock_get_receipt:
                RoutingSlipTask.link_routing_slips()
                mock_cfs_reverse.assert_called()
                mock_cfs_reverse.assert_called_with(cfs_account, child_rs.number, ReverseOperation.LINK.value)
                mock_create_cfs.assert_called()
                mock_get_receipt.assert_called()

    # child_rs = RoutingSlipModel.find_by_number(child_rs_number)
    # parent_rs = RoutingSlipModel.find_by_number(parent_rs_number)
    # PS This has changed, no longer updating child rs payment account with parent.
    # assert child_rs.payment_account_id == parent_rs.payment_account_id
    cfs_account: CfsAccountModel = CfsAccountModel.find_by_id(cfs_account.id)
    assert cfs_account.status == CfsAccountStatus.INACTIVE.value

    # make sure next invocation doesnt fetch any records
    with patch("pay_api.services.CFSService.reverse_rs_receipt_in_cfs") as mock_cfs_reverse:
        with patch("pay_api.services.CFSService.create_cfs_receipt") as mock_create_cfs:
            RoutingSlipTask.link_routing_slips()
            mock_cfs_reverse.assert_not_called()
            mock_create_cfs.assert_not_called()


def test_process_nsf(session):
    """Test process NSF."""
    # 1. Link 2 child routing slips with parent.
    # 2. Mark the parent as NSF and run job.
    child_1 = "123456789"
    child_2 = "987654321"
    parent = "111111111"
    factory_routing_slip_account(number=child_1, status=CfsAccountStatus.ACTIVE.value, total=10)
    factory_routing_slip_account(number=child_2, status=CfsAccountStatus.ACTIVE.value, total=10)
    pay_account = factory_routing_slip_account(number=parent, status=CfsAccountStatus.ACTIVE.value, total=10)

    child_1_rs = RoutingSlipModel.find_by_number(child_1)
    child_2_rs = RoutingSlipModel.find_by_number(child_2)
    parent_rs = RoutingSlipModel.find_by_number(parent)

    # Do Link
    for child in (child_2_rs, child_1_rs):
        child.status = RoutingSlipStatus.LINKED.value
        child.parent_number = parent_rs.number
        child.save()

    RoutingSlipTask.link_routing_slips()

    # Now mark the parent as NSF
    parent_rs.remaining_amount = -30
    parent_rs.status = RoutingSlipStatus.NSF.value
    parent_rs.save()

    # Create an invoice record against this routing slip.
    invoice = factory_invoice(
        payment_account=pay_account,
        total=30,
        paid=30,
        status_code=InvoiceStatus.PAID.value,
        payment_method_code=PaymentMethod.INTERNAL.value,
        routing_slip=parent_rs.number,
    )

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    # Create a distribution for NSF -> As this is a manual step once in each env.
    nsf_fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("BCR", "NSF")
    distribution = factory_distribution("NSF")
    factory_distribution_link(distribution.distribution_code_id, nsf_fee_schedule.fee_schedule_id)

    # Create invoice
    factory_invoice_reference(invoice.id, status_code=InvoiceReferenceStatus.COMPLETED.value)

    # Create receipts for the invoices
    factory_receipt(invoice.id, parent_rs.number)
    factory_receipt(invoice.id, child_1_rs.number)
    factory_receipt(invoice.id, child_2_rs.number)

    with patch("pay_api.services.CFSService.reverse_rs_receipt_in_cfs") as mock_cfs_reverse:
        RoutingSlipTask.process_nsf()
        mock_cfs_reverse.assert_called()

    # Assert the records.
    invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    assert invoice.invoice_status_code == InvoiceStatus.CREATED.value
    assert InvoiceReferenceModel.find_by_invoice_id_and_status(
        invoice.id, status_code=InvoiceReferenceStatus.ACTIVE.value
    )
    assert not ReceiptModel.find_all_receipts_for_invoice(invoice.id)
    assert float(RoutingSlipModel.find_by_number(parent_rs.number).remaining_amount) == -60  # Including NSF Fee

    with patch("pay_api.services.CFSService.reverse_rs_receipt_in_cfs") as mock_cfs_reverse_2:
        RoutingSlipTask.process_nsf()
        mock_cfs_reverse_2.assert_not_called()


def test_process_void(session):
    """Test Routing slip set to VOID."""
    # 1. Link 2 child routing slips with parent.
    # 2. Mark the parent as VOID and run job.
    child_1 = "123456789"
    child_2 = "987654321"
    parent = "111111111"
    factory_routing_slip_account(number=child_1, status=CfsAccountStatus.ACTIVE.value, total=10)
    factory_routing_slip_account(number=child_2, status=CfsAccountStatus.ACTIVE.value, total=10)
    factory_routing_slip_account(number=parent, status=CfsAccountStatus.ACTIVE.value, total=10)

    child_1_rs = RoutingSlipModel.find_by_number(child_1)
    child_2_rs = RoutingSlipModel.find_by_number(child_2)
    parent_rs = RoutingSlipModel.find_by_number(parent)

    # Do Link
    for child in (child_2_rs, child_1_rs):
        child.status = RoutingSlipStatus.LINKED.value
        child.parent_number = parent_rs.number
        child.save()

    RoutingSlipTask.link_routing_slips()

    # Now mark the parent as VOID
    parent_rs.status = RoutingSlipStatus.VOID.value
    parent_rs.save()

    with patch("pay_api.services.CFSService.reverse_rs_receipt_in_cfs") as mock_cfs_reverse:
        RoutingSlipTask.process_void()
        mock_cfs_reverse.assert_called()

    # Assert the records.
    assert float(RoutingSlipModel.find_by_number(parent_rs.number).remaining_amount) == 0

    with patch("pay_api.services.CFSService.reverse_rs_receipt_in_cfs") as mock_cfs_reverse_2:
        RoutingSlipTask.process_void()
        mock_cfs_reverse_2.assert_not_called()


def test_process_correction(session):
    """Test Routing slip set to CORRECTION."""
    number = "1111111"
    pay_account = factory_routing_slip_account(number=number, status=CfsAccountStatus.ACTIVE.value, total=10)
    # Create an invoice for the routing slip
    # Create an invoice record against this routing slip.
    invoice = factory_invoice(
        payment_account=pay_account,
        total=30,
        paid=30,
        status_code=InvoiceStatus.PAID.value,
        payment_method_code=PaymentMethod.INTERNAL.value,
        routing_slip=number,
    )

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    # Create invoice reference
    factory_invoice_reference(invoice.id, status_code=InvoiceReferenceStatus.COMPLETED.value)

    # Create receipts for the invoices
    factory_receipt(invoice.id, number)

    rs = RoutingSlipModel.find_by_number(number)
    rs.status = RoutingSlipStatus.CORRECTION.value
    rs.total = 900
    rs.save()

    session.commit()

    with patch("pay_api.services.CFSService.reverse_rs_receipt_in_cfs") as mock_reverse:
        with patch("pay_api.services.CFSService.create_cfs_receipt") as mock_create_receipt:
            with patch("pay_api.services.CFSService.get_invoice") as mock_get_invoice:
                RoutingSlipTask.process_correction()
                mock_reverse.assert_called()
                mock_get_invoice.assert_called()
                mock_create_receipt.assert_called()

    assert rs.status == RoutingSlipStatus.COMPLETE.value
    assert rs.cas_version_suffix == 2


def test_link_to_nsf_rs(session):
    """Test routing slip with NSF as parent."""
    child_rs_number = "1234"
    parent_rs_number = "89799"
    factory_routing_slip_account(number=child_rs_number, status=CfsAccountStatus.ACTIVE.value)
    pay_account = factory_routing_slip_account(number=parent_rs_number, status=CfsAccountStatus.ACTIVE.value)
    child_rs = RoutingSlipModel.find_by_number(child_rs_number)
    parent_rs = RoutingSlipModel.find_by_number(parent_rs_number)
    # Do Link
    child_rs.status = RoutingSlipStatus.LINKED.value
    child_rs.parent_number = parent_rs.number
    child_rs.save()

    # Run link process
    RoutingSlipTask.link_routing_slips()

    # Create an invoice for the routing slip
    # Create an invoice record against this routing slip.
    invoice = factory_invoice(
        payment_account=pay_account,
        total=30,
        paid=30,
        status_code=InvoiceStatus.PAID.value,
        payment_method_code=PaymentMethod.INTERNAL.value,
        routing_slip=parent_rs.number,
    )

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    # Create a distribution for NSF -> As this is a manual step once in each env.
    nsf_fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("BCR", "NSF")
    distribution = factory_distribution("NSF")
    factory_distribution_link(distribution.distribution_code_id, nsf_fee_schedule.fee_schedule_id)

    # Create invoice reference
    factory_invoice_reference(invoice.id, status_code=InvoiceReferenceStatus.COMPLETED.value)

    # Create receipts for the invoices
    factory_receipt(invoice.id, parent_rs.number)
    factory_receipt(invoice.id, child_rs.number)

    # Mark parent as NSF
    parent_rs.status = RoutingSlipStatus.NSF.value
    RoutingSlipTask.process_nsf()

    # Now create another RS and link it to the NSF RS, and assert status
    child_rs_2_number = "8888"
    factory_routing_slip_account(number=child_rs_2_number, status=CfsAccountStatus.ACTIVE.value)
    child_2_rs = RoutingSlipModel.find_by_number(child_rs_2_number)
    child_2_rs.status = RoutingSlipStatus.LINKED.value
    child_2_rs.parent_number = parent_rs.number
    child_2_rs.save()

    # Run link process
    with patch("pay_api.services.CFSService.reverse_rs_receipt_in_cfs"):
        RoutingSlipTask.link_routing_slips()

    # Now the invoice status should be PAID as RS has recovered.
    assert InvoiceModel.find_by_id(invoice.id).invoice_status_code == InvoiceStatus.PAID.value
    # Parent Routing slip status should be ACTIVE now
    assert RoutingSlipModel.find_by_number(parent_rs.number).status == RoutingSlipStatus.ACTIVE.value


@pytest.mark.parametrize(
    "rs_status",
    [
        RoutingSlipStatus.WRITE_OFF_AUTHORIZED.value,
        RoutingSlipStatus.REFUND_AUTHORIZED.value,
    ],
)
def test_receipt_adjustments(session, rs_status):
    """Test routing slip adjustments."""
    child_rs_number = "1234"
    parent_rs_number = "89799"
    factory_routing_slip_account(number=child_rs_number, status=CfsAccountStatus.ACTIVE.value, total=10)
    factory_routing_slip_account(
        number=parent_rs_number,
        status=CfsAccountStatus.ACTIVE.value,
        total=20,
        remaining_amount=20,
    )
    child_rs = RoutingSlipModel.find_by_number(child_rs_number)
    parent_rs = RoutingSlipModel.find_by_number(parent_rs_number)
    # Do Link
    child_rs.status = RoutingSlipStatus.LINKED.value
    child_rs.parent_number = parent_rs.number
    child_rs.save()

    parent_rs.status = rs_status
    parent_rs.save()

    # Test exception path first.
    with (
        patch("pay_api.services.CFSService.get_receipt") as mock_get_receipt,
        patch("pay_api.services.CFSService.adjust_receipt_to_zero") as mock_adjust,
    ):
        # Return different values for parent and child receipts
        mock_get_receipt.side_effect = [
            {
                "unapplied_amount": 0.0,  # parent
                "receipt_amount": 20.0,
                "invoices": [],
            },
            {
                "unapplied_amount": 0.0,  # child
                "receipt_amount": 10.0,
                "invoices": [],
            },
        ]
        mock_adjust.side_effect = Exception("ERROR!")
        RoutingSlipTask.adjust_routing_slips()

    parent_rs = RoutingSlipModel.find_by_number(parent_rs.number)
    assert parent_rs.remaining_amount == 20
    assert parent_rs.cas_mismatch is True

    parent_rs.cas_mismatch = False
    parent_rs.save()

    with (
        patch("pay_api.services.CFSService.get_receipt") as mock_get_receipt,
        patch("pay_api.services.CFSService.adjust_receipt_to_zero"),
    ):
        # Return different values for parent and child receipts
        mock_get_receipt.side_effect = [
            {
                "unapplied_amount": 20.0,  # parent
                "receipt_amount": 20.0,
                "invoices": [],
            },
            {
                "unapplied_amount": 10.0,  # child
                "receipt_amount": 10.0,
                "invoices": [],
            },
        ]
        RoutingSlipTask.adjust_routing_slips()

    parent_rs = RoutingSlipModel.find_by_number(parent_rs.number)
    assert parent_rs.remaining_amount == 0
    assert parent_rs.cas_mismatch is False


def test_receipt_adjustments_amount_mismatch(session):
    """Test routing slip adjustment fails when CFS amount doesn't match."""
    rs_number = "12346"
    factory_routing_slip_account(
        number=rs_number,
        status=CfsAccountStatus.ACTIVE.value,
        total=100,
        remaining_amount=50,
    )

    rs = RoutingSlipModel.find_by_number(rs_number)
    rs.status = RoutingSlipStatus.REFUND_AUTHORIZED.value
    rs.cas_mismatch = False
    rs.save()

    # doesn't match remaining_amount
    with (
        patch("pay_api.services.CFSService.get_receipt") as mock_get_receipt,
        patch("pay_api.services.CFSService.adjust_receipt_to_zero") as mock_adjust,
    ):
        mock_get_receipt.return_value = {"unapplied_amount": 30.0, "receipt_amount": 100.0, "invoices": []}

        RoutingSlipTask.adjust_routing_slips()

        rs = RoutingSlipModel.find_by_number(rs_number)
        assert rs.remaining_amount == 50
        assert not mock_adjust.called
        assert rs.cas_mismatch is True


def test_receipt_adjustments_data_mismatch(session):
    """Test routing slip adjustment fails when SBC-PAY and CFS data don't match."""
    rs_number = "12347"
    factory_routing_slip_account(
        number=rs_number,
        status=CfsAccountStatus.ACTIVE.value,
        total=100,
        remaining_amount=85,
    )

    rs = RoutingSlipModel.find_by_number(rs_number)
    rs.status = RoutingSlipStatus.REFUND_AUTHORIZED.value
    rs.cas_mismatch = False
    rs.save()

    # data mismatch
    with (
        patch("pay_api.services.CFSService.get_receipt") as mock_get_receipt,
        patch("pay_api.services.CFSService.adjust_receipt_to_zero") as mock_adjust,
    ):
        mock_get_receipt.return_value = {"unapplied_amount": 85.0, "receipt_amount": 100.0, "invoices": []}

        RoutingSlipTask.adjust_routing_slips()

        rs = RoutingSlipModel.find_by_number(rs_number)
        assert rs.remaining_amount == 85
        assert not mock_adjust.called
        assert rs.cas_mismatch is True


def test_receipt_adjustments_skip_cas_mismatch(session):
    """Test routing slip adjustment skips routing slips with cas_mismatch = True."""
    rs_number = "12348"
    factory_routing_slip_account(
        number=rs_number,
        status=CfsAccountStatus.ACTIVE.value,
        total=100,
        remaining_amount=50,
    )

    rs = RoutingSlipModel.find_by_number(rs_number)
    rs.status = RoutingSlipStatus.REFUND_AUTHORIZED.value
    rs.cas_mismatch = True
    rs.save()

    with (
        patch("pay_api.services.CFSService.get_receipt") as mock_get_receipt,
        patch("pay_api.services.CFSService.adjust_receipt_to_zero") as mock_adjust,
    ):
        RoutingSlipTask.adjust_routing_slips()

        assert not mock_get_receipt.called
        assert not mock_adjust.called

        rs = RoutingSlipModel.find_by_number(rs_number)
        assert rs.remaining_amount == 50
        assert rs.cas_mismatch is True


def test_receipt_adjustments_cfs_has_invoices_sbc_pay_doesnt(session):
    """Test routing slip adjustment fails when CFS has invoices but SBC-PAY doesn't."""
    rs_number = "12349"
    factory_routing_slip_account(
        number=rs_number,
        status=CfsAccountStatus.ACTIVE.value,
        total=100,
        remaining_amount=100,
    )

    rs = RoutingSlipModel.find_by_number(rs_number)
    rs.status = RoutingSlipStatus.REFUND_AUTHORIZED.value
    rs.cas_mismatch = False
    rs.save()

    with (
        patch("pay_api.services.CFSService.get_receipt") as mock_get_receipt,
        patch("pay_api.services.CFSService.adjust_receipt_to_zero") as mock_adjust,
    ):
        mock_get_receipt.return_value = {
            "unapplied_amount": 100.0,
            "receipt_amount": 100.0,
            "invoices": [{"invoice_number": "INV123", "amount": 50.0}],
        }

        RoutingSlipTask.adjust_routing_slips()

        rs = RoutingSlipModel.find_by_number(rs_number)
        assert rs.remaining_amount == 100
        assert not mock_adjust.called
        assert rs.cas_mismatch is True


def test_receipt_adjustments_with_multiple_invoices_consistent(session):
    """Test routing slip adjustment succeeds when both SBC-PAY and CFS have consistent invoice data."""
    rs_number = "12350"
    pay_account = factory_routing_slip_account(
        number=rs_number,
        status=CfsAccountStatus.ACTIVE.value,
        total=100.33,
        remaining_amount=67.11,
    )

    # These will be queried by _get_applied_invoices_amount() to calculate total applied: 33.22
    factory_invoice(
        payment_account=pay_account,
        total=22.11,
        paid=22.11,
        status_code=InvoiceStatus.PAID.value,
        payment_method_code=PaymentMethod.INTERNAL.value,
        routing_slip=rs_number,
    )
    factory_invoice(
        payment_account=pay_account,
        total=11.11,
        paid=11.11,
        status_code=InvoiceStatus.PAID.value,
        payment_method_code=PaymentMethod.INTERNAL.value,
        routing_slip=rs_number,
    )

    rs = RoutingSlipModel.find_by_number(rs_number)
    rs.status = RoutingSlipStatus.REFUND_AUTHORIZED.value
    rs.cas_mismatch = False
    rs.save()

    with (
        patch("pay_api.services.CFSService.get_receipt") as mock_get_receipt,
        patch("pay_api.services.CFSService.adjust_receipt_to_zero") as mock_adjust,
    ):
        # total: 100.33, applied: 33.22 (22.11 + 11.11), unapplied: 67.11
        mock_get_receipt.return_value = {
            "unapplied_amount": 67.11,
            "receipt_amount": 100.33,
            "invoices": [
                {
                    "invoice_number": "REG01036828",
                    "total": 22.11,
                    "amount_applied": 22.11,
                    "links": [{"rel": "self", "href": "https://xxx/invs/REG01036828/"}],
                },
                {
                    "invoice_number": "REG01036829",
                    "total": 11.11,
                    "amount_applied": 11.11,
                    "links": [{"rel": "self", "href": "https://xxx/invs/REG01036829/"}],
                },
            ],
        }

        RoutingSlipTask.adjust_routing_slips()

        rs = RoutingSlipModel.find_by_number(rs_number)

        assert rs.remaining_amount == 0
        assert mock_adjust.called

        assert rs.cas_mismatch is False


def test_receipt_adjustments_skip_child_pending_invoices(session):
    """Test routing slip adjustment skips when child routing slips have pending invoices."""
    child_rs_number = "12352"
    parent_rs_number = "12353"

    child_pay_account = factory_routing_slip_account(
        number=child_rs_number, status=CfsAccountStatus.ACTIVE.value, total=10
    )
    factory_routing_slip_account(
        number=parent_rs_number,
        status=CfsAccountStatus.ACTIVE.value,
        total=20,
        remaining_amount=20,
    )

    child_rs = RoutingSlipModel.find_by_number(child_rs_number)
    parent_rs = RoutingSlipModel.find_by_number(parent_rs_number)

    child_rs.status = RoutingSlipStatus.LINKED.value
    child_rs.parent_number = parent_rs.number
    child_rs.save()

    parent_rs.status = RoutingSlipStatus.REFUND_AUTHORIZED.value
    parent_rs.cas_mismatch = False
    parent_rs.save()

    factory_invoice(
        payment_account=child_pay_account,
        total=10,
        status_code=InvoiceStatus.CREATED.value,
        payment_method_code=PaymentMethod.INTERNAL.value,
        routing_slip=child_rs_number,
    )

    with (
        patch("pay_api.services.CFSService.get_receipt") as mock_get_receipt,
        patch("pay_api.services.CFSService.adjust_receipt_to_zero") as mock_adjust,
    ):
        RoutingSlipTask.adjust_routing_slips()

        assert not mock_get_receipt.called
        assert not mock_adjust.called

        parent_rs = RoutingSlipModel.find_by_number(parent_rs_number)
        assert parent_rs.remaining_amount == 20

        assert parent_rs.cas_mismatch is False


def test_apply_routing_slips_to_invoice_uses_decimal(session):
    """Test that apply_routing_slips_to_invoice uses Decimal for receipt amount calculations."""
    rs_number = "99999"
    pay_account = factory_routing_slip_account(number=rs_number, status=CfsAccountStatus.ACTIVE.value, total=100)
    rs = RoutingSlipModel.find_by_number(rs_number)
    payment_account = PaymentAccountModel.find_by_id(rs.payment_account_id)
    cfs_account = CfsAccountModel.find_effective_by_payment_method(payment_account.id, PaymentMethod.INTERNAL.value)

    invoice = factory_invoice(
        payment_account=pay_account,
        total=30,
        status_code=InvoiceStatus.CREATED.value,
        payment_method_code=PaymentMethod.INTERNAL.value,
        routing_slip=rs_number,
    )
    inv_ref = factory_invoice_reference(invoice.id, invoice_number="INV001")

    # Use values that would produce floating-point errors with float math:
    # float(100.01) - float(69.99) = 30.020000000000003 (float drift)
    # Decimal("100.01") - Decimal("69.99") = Decimal("30.02") (exact)
    mock_apply_response = MagicMock()
    mock_apply_response.json.return_value = {
        "receipt_number": rs_number,
        "unapplied_amount": 69.99,
    }

    with (
        patch.object(CFSService, "get_receipt", return_value={"unapplied_amount": 100.01}),
        patch.object(CFSService, "apply_receipt", return_value=mock_apply_response),
        patch.object(CFSService, "get_invoice", return_value={"amount_due": 0}),
    ):
        RoutingSlipTask.apply_routing_slips_to_invoice(
            payment_account, cfs_account, rs, invoice, inv_ref.invoice_number
        )

    receipts = ReceiptModel.find_all_receipts_for_invoice(invoice.id)
    assert len(receipts) == 1
    receipt = receipts[0]
    # Decimal math avoids float drift: 100.01 - 69.99 = 30.02 exactly
    # (with float math this would be 30.020000000000003)
    assert receipt.receipt_amount == 30.02
