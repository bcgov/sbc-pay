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
from pay_api.models import InvoiceSchema
from tests.utilities.base_test import factory_invoice, factory_payment, factory_payment_account


def test_invoice(session):
    """Assert a invoice is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment=payment, payment_account=payment_account)
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
    invoice = factory_invoice(payment=payment, payment_account=payment_account)
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
    invoice = factory_invoice(payment=payment, payment_account=payment_account)
    invoice.save()
    assert invoice.find_by_id_and_payment_id(invoice.id, payment.id) is not None
