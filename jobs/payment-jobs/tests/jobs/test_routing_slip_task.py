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
from unittest.mock import patch

import pytest
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.utils.enums import (
    CfsAccountStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, RoutingSlipStatus)

from tasks.routing_slip_task import RoutingSlipTask

from .factory import (
    factory_distribution, factory_distribution_link, factory_invoice, factory_invoice_reference,
    factory_payment_line_item, factory_receipt, factory_routing_slip_account)


def test_link_rs(session):
    """Test link routing slip."""
    child_rs_number = '1234'
    parent_rs_number = '89799'
    factory_routing_slip_account(number=child_rs_number, status=CfsAccountStatus.ACTIVE.value)
    factory_routing_slip_account(number=parent_rs_number, status=CfsAccountStatus.ACTIVE.value)
    child_rs = RoutingSlipModel.find_by_number(child_rs_number)
    parent_rs = RoutingSlipModel.find_by_number(parent_rs_number)
    # Do Link
    child_rs.status = RoutingSlipStatus.LINKED.value
    child_rs.parent_number = parent_rs.number
    child_rs.save()
    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(
        child_rs.payment_account_id)

    cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(
        payment_account.id)

    with patch('pay_api.services.CFSService.reverse_rs_receipt_in_cfs') as mock_cfs_reverse:
        with patch('pay_api.services.CFSService.create_cfs_receipt') as mock_create_cfs:
            RoutingSlipTask.link_routing_slips()
            mock_cfs_reverse.assert_called()
            mock_cfs_reverse.assert_called_with(cfs_account, child_rs.number)
            mock_create_cfs.assert_called()

    # child_rs = RoutingSlipModel.find_by_number(child_rs_number)
    # parent_rs = RoutingSlipModel.find_by_number(parent_rs_number)
    # PS This has changed, no longer updating child rs payment account with parent.
    # assert child_rs.payment_account_id == parent_rs.payment_account_id
    cfs_account: CfsAccountModel = CfsAccountModel.find_by_id(cfs_account.id)
    assert cfs_account.status == CfsAccountStatus.INACTIVE.value

    # make sure next invocation doesnt fetch any records
    with patch('pay_api.services.CFSService.reverse_rs_receipt_in_cfs') as mock_cfs_reverse:
        with patch('pay_api.services.CFSService.create_cfs_receipt') as mock_create_cfs:
            RoutingSlipTask.link_routing_slips()
            mock_cfs_reverse.assert_not_called()
            mock_create_cfs.assert_not_called()


def test_process_nsf(session):
    """Test process NSF."""
    # 1. Link 2 child routing slips with parent.
    # 2. Mark the parent as NSF and run job.
    child_1 = '123456789'
    child_2 = '987654321'
    parent = '111111111'
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
    invoice = factory_invoice(payment_account=pay_account, total=30,
                              status_code=InvoiceStatus.PAID.value,
                              payment_method_code=PaymentMethod.INTERNAL.value,
                              routing_slip=parent_rs.number)

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    # Create a distribution for NSF -> As this is a manual step once in each env.
    nsf_fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type('BCR', 'NSF')
    distribution = factory_distribution('NSF')
    factory_distribution_link(distribution.distribution_code_id, nsf_fee_schedule.fee_schedule_id)

    # Create invoice
    factory_invoice_reference(invoice.id, status_code=InvoiceReferenceStatus.COMPLETED.value)

    # Create receipts for the invoices
    factory_receipt(invoice.id, parent_rs.number)
    factory_receipt(invoice.id, child_1_rs.number)
    factory_receipt(invoice.id, child_2_rs.number)

    with patch('pay_api.services.CFSService.reverse_rs_receipt_in_cfs') as mock_cfs_reverse:
        RoutingSlipTask.process_nsf()
        mock_cfs_reverse.assert_called()

    # Assert the records.
    invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    assert invoice.invoice_status_code == InvoiceStatus.CREATED.value
    assert InvoiceReferenceModel.find_reference_by_invoice_id_and_status(
        invoice.id, status_code=InvoiceReferenceStatus.ACTIVE.value
    )
    assert not ReceiptModel.find_all_receipts_for_invoice(invoice.id)
    assert float(RoutingSlipModel.find_by_number(parent_rs.number).remaining_amount) == -60  # Including NSF Fee

    with patch('pay_api.services.CFSService.reverse_rs_receipt_in_cfs') as mock_cfs_reverse_2:
        RoutingSlipTask.process_nsf()
        mock_cfs_reverse_2.assert_not_called()


def test_link_to_nsf_rs(session):
    """Test routing slip with NSF as parent."""
    child_rs_number = '1234'
    parent_rs_number = '89799'
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
    invoice = factory_invoice(payment_account=pay_account, total=30,
                              status_code=InvoiceStatus.PAID.value,
                              payment_method_code=PaymentMethod.INTERNAL.value,
                              routing_slip=parent_rs.number)

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    # Create a distribution for NSF -> As this is a manual step once in each env.
    nsf_fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type('BCR', 'NSF')
    distribution = factory_distribution('NSF')
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
    child_rs_2_number = '8888'
    factory_routing_slip_account(number=child_rs_2_number, status=CfsAccountStatus.ACTIVE.value)
    child_2_rs = RoutingSlipModel.find_by_number(child_rs_2_number)
    child_2_rs.status = RoutingSlipStatus.LINKED.value
    child_2_rs.parent_number = parent_rs.number
    child_2_rs.save()

    # Run link process
    with patch('pay_api.services.CFSService.reverse_rs_receipt_in_cfs'):
        RoutingSlipTask.link_routing_slips()

    # Now the invoice status should be PAID as RS has recovered.
    assert InvoiceModel.find_by_id(invoice.id).invoice_status_code == InvoiceStatus.PAID.value
    # Parent Routing slip status should be ACTIVE now
    assert RoutingSlipModel.find_by_number(parent_rs.number).status == RoutingSlipStatus.ACTIVE.value


@pytest.mark.parametrize('rs_status', [
    RoutingSlipStatus.WRITE_OFF_AUTHORIZED.value, RoutingSlipStatus.REFUND_AUTHORIZED.value
])
def test_receipt_adjustments(session, rs_status):
    """Test routing slip adjustments."""
    child_rs_number = '1234'
    parent_rs_number = '89799'
    factory_routing_slip_account(number=child_rs_number, status=CfsAccountStatus.ACTIVE.value)
    factory_routing_slip_account(number=parent_rs_number, status=CfsAccountStatus.ACTIVE.value, total=10,
                                 remaining_amount=10)
    child_rs = RoutingSlipModel.find_by_number(child_rs_number)
    parent_rs = RoutingSlipModel.find_by_number(parent_rs_number)
    # Do Link
    child_rs.status = RoutingSlipStatus.LINKED.value
    child_rs.parent_number = parent_rs.number
    child_rs.save()

    parent_rs.status = rs_status

    # Test exception path first.
    with patch('pay_api.services.CFSService.adjust_receipt_to_zero') as mock:
        mock.side_effect = Exception('ERROR!')
        RoutingSlipTask.adjust_routing_slips()

    parent_rs = RoutingSlipModel.find_by_number(parent_rs.number)
    assert parent_rs.remaining_amount == 10

    with patch('pay_api.services.CFSService.adjust_receipt_to_zero'):
        RoutingSlipTask.adjust_routing_slips()

    parent_rs = RoutingSlipModel.find_by_number(parent_rs.number)
    assert parent_rs.remaining_amount == 0
