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

from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.paybc_service import PaybcService
from pay_api.factory.payment_system_factory import PaymentSystemFactory
import pytest
from pay_api.utils.errors import Error


def test_paybc_system_factory(session):
    """Assert a paybc service is returned."""
    instance = PaymentSystemFactory.create('CC', 'CP')
    assert isinstance(instance, PaybcService)
    assert isinstance(instance, PaymentSystemService)


def test_invalid_pay_system(session):
    from pay_api.exceptions import BusinessException

    with pytest.raises(BusinessException) as excinfo:
        PaymentSystemFactory.create(None, None)
    assert excinfo.value.status == Error.PAY003.status
    assert excinfo.value.message == Error.PAY003.message
    assert excinfo.value.code == Error.PAY003.name

    with pytest.raises(BusinessException) as excinfo:
        PaymentSystemFactory.create('XXX', 'XXX')
    assert excinfo.value.status == Error.PAY003.status
    assert excinfo.value.message == Error.PAY003.message
    assert excinfo.value.code == Error.PAY003.name

