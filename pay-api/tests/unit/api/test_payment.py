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

"""Tests to assure the accounts end-point.

Test-Suite to ensure that the /accounts endpoint is working as expected.
"""
import json
from datetime import datetime

from pay_api.models.payment_account import PaymentAccount
from pay_api.utils.enums import PaymentMethod, Role
from tests.utilities.base_test import (
    factory_invoice, factory_invoice_reference, factory_payment, factory_payment_account, factory_payment_line_item,
    get_claims, token_header)


def test_account_payments(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    inv_number = 'REG00001'
    payment_account = factory_payment_account().save()

    invoice_1 = factory_invoice(payment_account)
    invoice_1.save()
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number).save()

    payment_1 = factory_payment(payment_status_code='CREATED',
                                payment_account_id=payment_account.id, invoice_number=inv_number)
    payment_1.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    rv = client.get(f'/api/v1/accounts/{auth_account_id}/payments', headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('total') == 1
    rv = client.get(f'/api/v1/accounts/{auth_account_id}/payments?status=FAILED', headers=headers)
    assert rv.status_code == 200
    assert rv.json.get('total') == 0


def test_create_account_payments(session, client, jwt, app):
    """Assert that the endpoint returns 200."""
    token = jwt.create_jwt(get_claims(), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}

    inv_number_1 = 'REG00001'
    payment_account = factory_payment_account().save()
    invoice_1 = factory_invoice(payment_account, total=100)
    invoice_1.save()
    factory_payment_line_item(invoice_id=invoice_1.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number_1).save()
    payment_1 = factory_payment(payment_status_code='FAILED',
                                payment_account_id=payment_account.id,
                                invoice_number=inv_number_1,
                                invoice_amount=100,
                                payment_method_code=PaymentMethod.PAD.value)
    payment_1.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    rv = client.post(f'/api/v1/accounts/{auth_account_id}/payments?retryFailedPayment=true', headers=headers)
    assert rv.status_code == 201


def test_create_eft_payment(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(roles=[Role.CREATE_CREDITS.value, Role.STAFF.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payload = {
        'paidAmount': 100,
        'paymentDate': str(datetime.now()),
        'paymentMethod': 'EFT'
    }
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value).save()
    rv = client.post(f'/api/v1/accounts/{payment_account.auth_account_id}/payments', headers=headers,
                     data=json.dumps(payload))
    assert rv.status_code == 201
    assert rv.json.get('paymentMethod') == PaymentMethod.EFT.value


def test_create_wire_payment(session, client, jwt, app):
    """Assert that the endpoint returns 201."""
    token = jwt.create_jwt(get_claims(roles=[Role.CREATE_CREDITS.value, Role.STAFF.value]), token_header)
    headers = {'Authorization': f'Bearer {token}', 'content-type': 'application/json'}
    payload = {
        'paidAmount': 100,
        'paymentDate': str(datetime.now()),
        'paymentMethod': 'WIRE'
    }
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.WIRE.value).save()
    rv = client.post(f'/api/v1/accounts/{payment_account.auth_account_id}/payments', headers=headers,
                     data=json.dumps(payload))
    assert rv.status_code == 201
    assert rv.json.get('paymentMethod') == PaymentMethod.WIRE.value
