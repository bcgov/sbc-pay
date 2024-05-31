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

"""Tests to assure the CorpType Class.

Test-Suite to ensure that the CorpType Class is working as expected.
"""

from pay_api.models import Payment


def factory_payment(payment_system_code: str = 'PAYBC', payment_method_code='CC', payment_status_code='CREATED'):
    """Return Factory."""
    return Payment(payment_system_code=payment_system_code, payment_method_code=payment_method_code,
                   payment_status_code=payment_status_code)


def test_payment(session):
    """Assert a payment is stored.

    Start with a blank database.
    """
    payment = factory_payment()
    payment.save()
    assert payment.id is not None


def test_payment_usd_payment(session):
    """Assert a payment with usd payment is stored.

    Start with a blank database.
    """
    payment = Payment(payment_system_code='PAYBC', payment_method_code='CC',
                      payment_status_code='CREATED', paid_usd_amount=100)
    payment.save()
    assert payment.id is not None
    assert payment.paid_usd_amount == 100
