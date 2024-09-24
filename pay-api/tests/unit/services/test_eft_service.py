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

"""Tests to assure the EFT service layer.

Test-Suite to ensure that the EFT Service is working as expected.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from pay_api.exceptions import BusinessException
from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTCreditInvoiceLink as EFTCreditInvoiceLinkModel
from pay_api.models import EFTShortnamesHistorical as EFTHistoryModel
from pay_api.services.eft_service import EftService
from pay_api.services.eft_refund import EFTRefund as EFTRefundService
from pay_api.utils.enums import (
    EFTCreditInvoiceStatus, EFTHistoricalTypes, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod)
from pay_api.utils.errors import Error
from tests.utilities.base_test import (
    factory_eft_credit, factory_eft_credit_invoice_link, factory_eft_file, factory_eft_shortname, factory_invoice,
    factory_invoice_reference, factory_payment_account)


eft_service = EftService()


def test_get_payment_system_code(session):
    """Test get_payment_system_code."""
    code = eft_service.get_payment_system_code()
    assert code == 'PAYBC'


def test_get_payment_method_code(session):
    """Test get_payment_method_code."""
    code = eft_service.get_payment_method_code()
    assert code == 'EFT'


def test_has_no_payment_blockers(session):
    """Test for no payment blockers."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value)
    payment_account.save()
    eft_service.ensure_no_payment_blockers(payment_account)
    assert True


def test_has_payment_blockers(session):
    """Test has payment blockers."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value)
    payment_account.has_overdue_invoices = datetime.now(tz=timezone.utc)
    payment_account.save()

    with pytest.raises(BusinessException):
        eft_service.ensure_no_payment_blockers(payment_account)
    assert True


def test_refund_eft_credits(session):
    """Test the _refund_eft_credits method."""
    credit1 = MagicMock(remaining_amount=2)
    credit2 = MagicMock(remaining_amount=4)
    credit3 = MagicMock(remaining_amount=3)

    with patch('pay_api.models.EFTCredit.get_eft_credits',
               return_value=[credit1, credit2, credit3]), \
         patch('pay_api.models.EFTCredit.get_eft_credit_balance', return_value=9):
        EFTRefundService.refund_eft_credits(1, 8)
        assert credit1.remaining_amount == 0
        assert credit2.remaining_amount == 0
        assert credit3.remaining_amount == 1

        credit1.remaining_amount = 5
        credit2.remaining_amount = 5

        with patch('pay_api.models.EFTCredit.get_eft_credit_balance', return_value=10):
            EFTRefundService.refund_eft_credits(1, 7)
            assert credit1.remaining_amount == 0
            assert credit2.remaining_amount == 3

        credit1.remaining_amount = 5
        credit2.remaining_amount = 2

        with patch('pay_api.models.EFTCredit.get_eft_credit_balance', return_value=7):
            EFTRefundService.refund_eft_credits(1, 1)
            assert credit1.remaining_amount == 4
            assert credit2.remaining_amount == 2


@pytest.mark.parametrize('test_name', [
    ('reverse_eft_credit_success'),
    ('reverse_eft_credit_leftover_fail'),
    ('reverse_eft_credit_remaining_higher_than_original_amount_fail'),
])
def test_refund_eft_credit_reversal(session, test_name):
    """Test refund eft credit reversal."""
    file = factory_eft_file().save()
    short_name = factory_eft_shortname(short_name='TESTSHORTNAME123').save()
    match test_name:
        case 'reverse_eft_credit_success':
            factory_eft_credit(eft_file_id=file.id, short_name_id=short_name.id, amount=10, remaining_amount=10)
            factory_eft_credit(eft_file_id=file.id, short_name_id=short_name.id, amount=10, remaining_amount=7)
            factory_eft_credit(eft_file_id=file.id, short_name_id=short_name.id, amount=10, remaining_amount=9)
            factory_eft_credit(eft_file_id=file.id, short_name_id=short_name.id, amount=1, remaining_amount=0)
            EFTRefundService.reverse_eft_credits(short_name.id, 5)
            assert EFTCreditModel.query.filter_by(remaining_amount=10).count() == 3
            assert EFTCreditModel.query.filter_by(remaining_amount=1).count() == 1
        case 'reverse_eft_credit_leftover_fail':
            factory_eft_credit(eft_file_id=file.id, short_name_id=short_name.id, amount=10, remaining_amount=10)
            factory_eft_credit(eft_file_id=file.id, short_name_id=short_name.id, amount=10, remaining_amount=9)
            with pytest.raises(BusinessException) as excinfo:
                EFTRefundService.reverse_eft_credits(short_name.id, 5)
                assert excinfo.value.code == Error.INVALID_REFUND.name
        case 'reverse_eft_credit_remaining_higher_than_original_amount_fail':
            factory_eft_credit(eft_file_id=file.id, short_name_id=short_name.id, amount=10, remaining_amount=15)
            with pytest.raises(BusinessException) as excinfo:
                EFTRefundService.reverse_eft_credits(short_name.id, 5)
                assert excinfo.value.code == Error.INVALID_REFUND.name


def test_refund_eft_credits_exceed_balance(session):
    """Test refund amount exceeds eft_credit_balance."""
    credit1 = MagicMock(remaining_amount=2)
    credit2 = MagicMock(remaining_amount=4)
    credit3 = MagicMock(remaining_amount=3)

    with patch('pay_api.models.EFTCredit.get_eft_credits',
               return_value=[credit1, credit2, credit3]), \
         patch('pay_api.models.EFTCredit.get_eft_credit_balance', return_value=8):

        with pytest.raises(BusinessException) as excinfo:
            EFTRefundService.refund_eft_credits(1, 20)

        assert excinfo.value.code == Error.INVALID_REFUND.name


@pytest.mark.parametrize('test_name', [
    ('0_no_invoice_reference_cil_exists'),
    ('1_invoice_non_exist'),
    ('2_no_eft_credit_link'),
    ('3_pending_credit_link'),
    ('4_completed_credit_link'),
    ('5_consolidated_invoice_block')
])
def test_eft_invoice_refund(session, test_name):
    """Test various scenarios for eft_invoice_refund."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value)
    invoice = factory_invoice(payment_account=payment_account,
                              status_code=InvoiceStatus.APPROVED.value,
                              total=5).save()
    eft_file = factory_eft_file().save()
    short_name = factory_eft_shortname(short_name='TESTSHORTNAME123').save()
    eft_credit = factory_eft_credit(eft_file_id=eft_file.id,
                                    short_name_id=short_name.id,
                                    amount=10,
                                    remaining_amount=1).save()
    match test_name:
        case '0_no_invoice_reference_cil_exists':
            cil_1 = factory_eft_credit_invoice_link(invoice_id=invoice.id,
                                                    eft_credit_id=eft_credit.id,
                                                    status_code=EFTCreditInvoiceStatus.PENDING.value,
                                                    link_group_id=2).save()
        case '1_invoice_non_exist':
            pass
        case '2_no_eft_credit_link':
            factory_invoice_reference(invoice_id=invoice.id, invoice_number='1234').save()
        case '3_pending_credit_link':
            factory_invoice_reference(invoice_id=invoice.id, invoice_number='1234').save()
            # Filler rows to make sure PENDING is the highest ID
            cil_1 = factory_eft_credit_invoice_link(invoice_id=invoice.id,
                                                    eft_credit_id=eft_credit.id,
                                                    status_code=EFTCreditInvoiceStatus.COMPLETED.value,
                                                    link_group_id=1).save()
            cil_2 = factory_eft_credit_invoice_link(invoice_id=invoice.id,
                                                    eft_credit_id=eft_credit.id,
                                                    status_code=EFTCreditInvoiceStatus.REFUNDED.value,
                                                    link_group_id=2).save()
            cil_3 = factory_eft_credit_invoice_link(invoice_id=invoice.id,
                                                    eft_credit_id=eft_credit.id,
                                                    status_code=EFTCreditInvoiceStatus.PENDING.value,
                                                    link_group_id=3).save()
            cil_4 = factory_eft_credit_invoice_link(invoice_id=invoice.id,
                                                    eft_credit_id=eft_credit.id,
                                                    status_code=EFTCreditInvoiceStatus.PENDING.value,
                                                    link_group_id=3).save()
        case '4_completed_credit_link' | '5_consolidated_invoice_block':
            invoice_reference = factory_invoice_reference(invoice_id=invoice.id,
                                                          invoice_number='1234').save()
            if test_name == '5_consolidated_invoice_block':
                invoice_reference.is_consolidated = True
                invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value
                invoice_reference.save()
            # Filler rows to make sure COMPLETED is the highest ID
            cil_1 = factory_eft_credit_invoice_link(invoice_id=invoice.id,
                                                    eft_credit_id=eft_credit.id,
                                                    status_code=EFTCreditInvoiceStatus.REFUNDED.value,
                                                    link_group_id=1).save()
            # This row has a different link_group_id, it wont be included.
            cil_2 = factory_eft_credit_invoice_link(invoice_id=invoice.id,
                                                    eft_credit_id=eft_credit.id,
                                                    status_code=EFTCreditInvoiceStatus.COMPLETED.value,
                                                    link_group_id=5).save()
            cil_3 = factory_eft_credit_invoice_link(invoice_id=invoice.id,
                                                    eft_credit_id=eft_credit.id,
                                                    status_code=EFTCreditInvoiceStatus.COMPLETED.value,
                                                    link_group_id=2).save()
            cil_4 = factory_eft_credit_invoice_link(invoice_id=invoice.id,
                                                    eft_credit_id=eft_credit.id,
                                                    status_code=EFTCreditInvoiceStatus.COMPLETED.value,
                                                    link_group_id=2).save()
            cil_5 = factory_eft_credit_invoice_link(invoice_id=invoice.id,
                                                    eft_credit_id=eft_credit.id,
                                                    status_code=EFTCreditInvoiceStatus.COMPLETED.value,
                                                    link_group_id=2).save()
        case _:
            raise NotImplementedError

    if test_name == '5_consolidated_invoice_block':
        with pytest.raises(BusinessException) as excinfo:
            invoice.invoice_status_code = eft_service.process_cfs_refund(invoice, payment_account, None)
            invoice.save()
        assert excinfo.value.code == Error.INVALID_CONSOLIDATED_REFUND.name
        return

    invoice.invoice_status_code = eft_service.process_cfs_refund(invoice, payment_account, None)
    invoice.save()

    match test_name:
        case '0_no_invoice_reference_cil_exists':
            assert invoice
            assert invoice.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value
            assert cil_1.status_code == EFTCreditInvoiceStatus.CANCELLED.value
            eft_history = session.query(EFTHistoryModel).one()
            assert_shortname_refund_history(eft_credit, eft_history, invoice)
        case '1_invoice_non_exist':
            assert invoice
            assert invoice.invoice_status_code == InvoiceStatus.CANCELLED.value
            assert session.query(EFTHistoryModel).one_or_none() is None
        case '2_no_eft_credit_link':
            assert invoice
            assert invoice.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value
            assert session.query(EFTHistoryModel).one_or_none() is None
        case '3_pending_credit_link':
            assert invoice
            assert invoice.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value
            assert cil_1.status_code == EFTCreditInvoiceStatus.COMPLETED.value
            assert cil_2.status_code == EFTCreditInvoiceStatus.REFUNDED.value
            assert cil_3.status_code == EFTCreditInvoiceStatus.CANCELLED.value
            assert cil_4.status_code == EFTCreditInvoiceStatus.CANCELLED.value
            assert eft_credit.remaining_amount == 3
            eft_history = session.query(EFTHistoryModel).one()
            assert_shortname_refund_history(eft_credit, eft_history, invoice)
        case '4_completed_credit_link':
            assert invoice
            assert invoice.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value
            assert cil_1.status_code == EFTCreditInvoiceStatus.REFUNDED.value
            assert cil_2.status_code == EFTCreditInvoiceStatus.COMPLETED.value
            assert cil_3.status_code == EFTCreditInvoiceStatus.COMPLETED.value
            assert cil_4.status_code == EFTCreditInvoiceStatus.COMPLETED.value
            assert cil_5.status_code == EFTCreditInvoiceStatus.COMPLETED.value
            assert eft_credit.remaining_amount == 4
            assert EFTCreditInvoiceLinkModel.query.count() == 5 + 3
            pending_refund_count = 0
            for cil in EFTCreditInvoiceLinkModel.query.all():
                if cil.status_code == EFTCreditInvoiceStatus.PENDING_REFUND.value:
                    pending_refund_count += 1
            assert pending_refund_count == 3
            eft_history = session.query(EFTHistoryModel).one()
            assert_shortname_refund_history(eft_credit, eft_history, invoice)
        case _:
            raise NotImplementedError


def assert_shortname_refund_history(eft_credit, eft_history, invoice):
    """Assert EFT Short name record for invoice refund."""
    assert eft_history.credit_balance == eft_credit.remaining_amount
    assert eft_history.is_processing is True
    assert eft_history.amount == invoice.total
    assert eft_history.transaction_type == EFTHistoricalTypes.INVOICE_REFUND.value
