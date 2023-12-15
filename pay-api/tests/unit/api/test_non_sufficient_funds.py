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

"""Tests to assure the Non-Sufficient Funds end-point.

Test-Suite to ensure that the /nsf endpoint is working as expected.
"""
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.utils.enums import InvoiceStatus
from tests.utilities.base_test import (
    factory_invoice, factory_invoice_reference, factory_non_sufficient_funds, factory_payment, factory_payment_account,
    factory_payment_line_item, get_claims, token_header)


def test_get_non_sufficient_funds(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    invoice_number = '10001'
    payment_account = factory_payment_account()
    payment_account.save()
    payment = factory_payment(payment_account_id=payment_account.id, paid_amount=0, invoice_number=invoice_number)
    payment.save()
    invoice = factory_invoice(
        payment_account=payment_account, status_code=InvoiceStatus.SETTLEMENT_SCHEDULED.value, paid=0, total=0)
    invoice.save()
    
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line_item = factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id,
                                          description='NSF', total=30)
    line_item.save()
    
    invoice_reference = factory_invoice_reference(invoice_id=invoice.id, invoice_number=invoice_number)
    invoice_reference.save()
    non_sufficient_funds = factory_non_sufficient_funds(invoice_id=invoice.id, description='NSF')
    non_sufficient_funds.save()

    nsf = client.get(f'/api/v1/accounts/{payment_account.auth_account_id}/nsf', headers=headers)
    assert nsf.status_code == 200
    assert len(nsf.json.get('items')) == 1
    assert nsf.json.get('total') == 1
    assert nsf.json.get('totalAmount') == 0
    assert nsf.json.get('totalAmountRemaining') == 30
    assert nsf.json.get('nsfAmount') == 30
