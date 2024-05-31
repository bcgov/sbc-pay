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

from pay_api.models.payment_system import PaymentSystem


def factory_payment_system(code: str = 'PAYBC', description='PayBC'):
    """Return Factory."""
    return PaymentSystem(code=code, description=description)


def test_payment_system(session):
    """Assert a payment_system is stored.

    Start with a blank database.
    """
    payment_method = factory_payment_system(code='XX', description='TEST')
    payment_method.save()
    assert payment_method.code == 'XX'
