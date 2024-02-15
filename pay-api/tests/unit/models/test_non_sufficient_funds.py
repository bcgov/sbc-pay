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

"""Tests to assure the Non-Sufficient Funds Class.

Test-Suite to ensure that the Non-Sufficient Funds Class is working as expected.
"""

from tests.utilities.base_test import (
    factory_invoice, factory_non_sufficient_funds, factory_payment, factory_payment_account)


def test_non_sufficient_funds(session):
    """Assert Non-Sufficient Funds defaults are stored."""
    payment_account = factory_payment_account()
    payment = factory_payment(invoice_number='REG00000001')
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account=payment_account)
    invoice.save()
    non_sufficient_funds = factory_non_sufficient_funds(
        invoice_id=invoice.id, invoice_number=payment.invoice_number, description='NSF')
    non_sufficient_funds.save()

    assert non_sufficient_funds.id is not None
    assert non_sufficient_funds.description == 'NSF'
    assert non_sufficient_funds.invoice_id is not None
    assert non_sufficient_funds.invoice_number == 'REG00000001'
