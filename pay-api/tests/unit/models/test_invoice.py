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

"""Tests to assure the CorpType Class.

Test-Suite to ensure that the CorpType Class is working as expected.
"""

from datetime import datetime

from pay_api.models import Invoice, InvoiceSchema, Payment, PaymentAccount


def factory_payment_account(corp_number: str = 'CP1234', corp_type_code='CP', payment_system_code='PAYBC'):
    """Factory."""
    return PaymentAccount(corp_number=corp_number, corp_type_code=corp_type_code,
                          payment_system_code=payment_system_code)


def factory_payment(payment_system_code: str = 'PAYBC', payment_method_code='CC', payment_status_code='DRAFT'):
    """Factory."""
    return Payment(payment_system_code=payment_system_code, payment_method_code=payment_method_code,
                   payment_status_code=payment_status_code, created_by='test', created_on=datetime.now())


def factory_invoice(payment_id: str, account_id: str):
    """Factory."""
    return Invoice(payment_id=payment_id,
                   invoice_status_code='DRAFT',
                   account_id=account_id,
                   total=0, created_by='test', created_on=datetime.now())


def test_invoice(session):
    """Assert a invoice is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_id=payment.id, account_id=payment_account.id)
    invoice.save()
    assert invoice.id is not None


def test_invoice_find_by_id(session):
    """Assert a invoice is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_id=payment.id, account_id=payment_account.id)
    invoice.save()
    assert invoice.find_by_id(invoice.id) is not None
    schema = InvoiceSchema()
    d = schema.dump(invoice)
    assert d.get('id') == invoice.id


def test_invoice_find_by_id_and_payment_id(session):
    """Assert a invoice is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_id=payment.id, account_id=payment_account.id)
    invoice.save()
    assert invoice.find_by_id_and_payment_id(invoice.id, payment.id) is not None
