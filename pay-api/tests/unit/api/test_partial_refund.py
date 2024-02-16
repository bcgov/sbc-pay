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

"""Tests to assure the refund end-point can handle partial refunds.

Test-Suite to ensure that the refunds endpoint for partials is working as expected.
"""
import json
from typing import List

from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import Refund as RefundModel
from pay_api.models import RefundsPartial as RefundPartialModel
from pay_api.utils.constants import REFUND_SUCCESS_MESSAGES
from pay_api.utils.enums import InvoiceStatus, RefundsPartialType, Role
from pay_api.utils.errors import Error
from tests.utilities.base_test import get_claims, get_payment_request, token_header


def test_create_refund(session, client, jwt, app, stan_server, monkeypatch):
    """Assert that the endpoint  returns 202."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()),
                     headers=headers)
    inv_id = rv.json.get('id')
    invoice: InvoiceModel = InvoiceModel.find_by_id(inv_id)

    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    receipt_number = '123451'
    rv = client.post(f'/api/v1/payment-requests/{inv_id}/transactions', data=json.dumps(data),
                     headers=headers)
    txn_id = rv.json.get('id')
    client.patch(f'/api/v1/payment-requests/{inv_id}/transactions/{txn_id}',
                 data=json.dumps({'receipt_number': receipt_number}), headers=headers)

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    payment_line_items: List[PaymentLineItemModel] = invoice.payment_line_items
    refund_amount = float(payment_line_items[0].filing_fees / 2)
    refund_revenue = [{'paymentLineItemId': payment_line_items[0].id,
                      'refundAmount': refund_amount,
                       'refundType': RefundsPartialType.OTHER_FEES.value}
                      ]

    rv = client.post(f'/api/v1/payment-requests/{inv_id}/refunds',
                     data=json.dumps({'reason': 'Test',
                                      'refundRevenue': refund_revenue
                                      }),
                     headers=headers)
    assert rv.status_code == 202
    assert rv.json.get('message') == REFUND_SUCCESS_MESSAGES['DIRECT_PAY.PAID']
    assert RefundModel.find_by_invoice_id(inv_id) is not None

    refunds_partial: List[RefundPartialModel] = RefundPartialModel.find_by_invoice_id(inv_id)
    assert refunds_partial
    assert len(refunds_partial) == 1

    refund = refunds_partial[0]
    assert refund.id is not None
    assert refund.payment_line_item_id == payment_line_items[0].id
    assert refund.refund_amount == refund_amount
    assert refund.refund_type == RefundsPartialType.OTHER_FEES.value


def test_create_refund_fails(session, client, jwt, app, stan_server, monkeypatch):
    """Assert that the endpoint returns 400."""
    token = jwt.create_jwt(get_claims(app_request=app), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    rv = client.post('/api/v1/payment-requests', data=json.dumps(get_payment_request()), headers=headers)
    inv_id = rv.json.get('id')

    data = {
        'clientSystemUrl': 'http://localhost:8080/coops-web/transactions/transaction_id=abcd',
        'payReturnUrl': 'http://localhost:8080/pay-web'
    }
    receipt_number = '123451'
    rv = client.post(f'/api/v1/payment-requests/{inv_id}/transactions', data=json.dumps(data),
                     headers=headers)
    txn_id = rv.json.get('id')
    client.patch(f'/api/v1/payment-requests/{inv_id}/transactions/{txn_id}',
                 data=json.dumps({'receipt_number': receipt_number}), headers=headers)

    invoice = InvoiceModel.find_by_id(inv_id)
    invoice.invoice_status_code = InvoiceStatus.APPROVED.value
    invoice.save()

    payment_line_items: List[PaymentLineItemModel] = invoice.payment_line_items
    refund_amount = float(payment_line_items[0].filing_fees / 2)
    refund_revenue = [{'paymentLineItemId': payment_line_items[0].id,
                       'refundAmount': refund_amount,
                       'refundType': RefundsPartialType.OTHER_FEES.value}
                      ]

    token = jwt.create_jwt(get_claims(app_request=app, role=Role.SYSTEM.value), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    rv = client.post(f'/api/v1/payment-requests/{inv_id}/refunds',
                     data=json.dumps({'reason': 'Test',
                                      'refundRevenue': refund_revenue
                                      }),
                     headers=headers)
    assert rv.status_code == 400
    assert rv.json.get('type') == Error.INVALID_REQUEST.name
    assert RefundModel.find_by_invoice_id(inv_id) is None

    refunds_partial: List[RefundPartialModel] = RefundPartialModel.find_by_invoice_id(inv_id)
    assert not refunds_partial
    assert len(refunds_partial) == 0
