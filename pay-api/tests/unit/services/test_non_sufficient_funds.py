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

"""Tests to assure the Non-Sufficient Funds service layer.

Test-Suite to ensure that the Non-Sufficient Funds layer is working as expected.
"""

from pay_api.models import FeeSchedule
from pay_api.services import NonSufficientFundsService
from pay_api.utils.enums import InvoiceStatus
from tests.utilities.base_test import (
    factory_invoice_reference, factory_invoice, factory_non_sufficient_funds, factory_payment,
    factory_payment_account, factory_payment_line_item)


def test_save_non_sufficient_funds(session):
    """Test save_non_sufficient_funds."""
    non_sufficient_funds_object = {
        'invoice_id': 1,
        'description': 'NSF',
    }
    non_sufficient_funds = NonSufficientFundsService.save_non_sufficient_funds(invoice_id=1,
                                                                               description='NSF')
    assert non_sufficient_funds
    assert non_sufficient_funds.invoice_id == non_sufficient_funds_object.get('invoice_id')
    assert non_sufficient_funds.description == non_sufficient_funds_object.get('description')


def test_find_all_non_sufficient_funds_invoices(session):
    """Test find_all_non_sufficient_funds_invoices."""
    invoice_number = '10001'
    payment_account = factory_payment_account()
    payment_account.save()
    payment = factory_payment(payment_account_id=payment_account.id, paid_amount=1, invoice_number=invoice_number)
    payment.save()
    invoice = factory_invoice(
        payment_account=payment_account, status_code=InvoiceStatus.SETTLEMENT_SCHEDULED.value, paid=1, total=200)
    invoice.save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id, description='NSF',
                              total=100)
    factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number).save()
    factory_non_sufficient_funds(invoice_id=invoice.id, description='NSF').save()

    non_sufficient_funds = NonSufficientFundsService.find_all_non_sufficient_funds_invoices(
        account_id=payment_account.auth_account_id)
    
    assert non_sufficient_funds
    assert non_sufficient_funds.get('invoices') is not None
    assert non_sufficient_funds.get('total_amount') is not None
    assert non_sufficient_funds.get('total_amount_remaining') is not None
    assert non_sufficient_funds.get('total_nsf_amount') is not None
    assert non_sufficient_funds.get('total_nsf_count') is not None
