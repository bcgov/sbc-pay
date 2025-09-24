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

from datetime import UTC, datetime, timedelta

import pytest
from flask import current_app
from freezegun import freeze_time

from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.bcol_service import BcolService
from pay_api.services.direct_pay_service import DirectPayService
from pay_api.services.eft_service import EftService
from pay_api.services.internal_pay_service import InternalPayService
from pay_api.services.pad_service import PadService
from pay_api.services.paybc_service import PaybcService
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.utils.enums import PaymentMethod
from pay_api.utils.errors import Error
from tests.utilities.base_test import get_unlinked_pad_account_payload


def test_paybc_system_factory(session, public_user_mock):
    """Assert a paybc service is returned."""
    from pay_api.factory.payment_system_factory import PaymentSystemFactory  # noqa I001; errors out the test case

    # Test for CC and CP
    instance = PaymentSystemFactory.create(payment_method="CC", corp_type="CP")
    assert isinstance(instance, PaybcService)
    assert isinstance(instance, PaymentSystemService)

    # Test for CC and CP
    instance = PaymentSystemFactory.create(payment_method=PaymentMethod.DIRECT_PAY.value, corp_type="CP")
    assert isinstance(instance, DirectPayService)
    assert isinstance(instance, PaymentSystemService)

    # Test for CC and CP with zero fees
    instance = PaymentSystemFactory.create(fees=0, payment_method="CC", corp_type="CP")
    assert isinstance(instance, InternalPayService)
    assert isinstance(instance, PaymentSystemService)

    # Test for PAYBC Service
    instance = PaymentSystemFactory.create_from_payment_method(PaymentMethod.CC.value)
    assert isinstance(instance, PaybcService)
    assert isinstance(instance, PaymentSystemService)

    # Test for Direct Pay Service
    instance = PaymentSystemFactory.create_from_payment_method(PaymentMethod.DIRECT_PAY.value)
    assert isinstance(instance, DirectPayService)
    assert isinstance(instance, PaymentSystemService)

    # Test for Internal Service
    instance = PaymentSystemFactory.create_from_payment_method(PaymentMethod.INTERNAL.value)
    assert isinstance(instance, InternalPayService)
    assert isinstance(instance, PaymentSystemService)

    # Test for BCOL Service
    instance = PaymentSystemFactory.create_from_payment_method(PaymentMethod.DRAWDOWN.value)
    assert isinstance(instance, BcolService)
    assert isinstance(instance, PaymentSystemService)

    # Test for EFT Service
    instance = PaymentSystemFactory.create_from_payment_method(PaymentMethod.EFT.value)
    assert isinstance(instance, EftService)
    assert isinstance(instance, PaymentSystemService)


def test_internal_staff_factory(session, staff_user_mock):
    """Test payment system creation for staff users."""
    from pay_api.factory.payment_system_factory import PaymentSystemFactory  # noqa I001; errors out the test case

    # Test for CC and CP with staff role
    instance = PaymentSystemFactory.create(payment_method="CC")
    assert isinstance(instance, InternalPayService)
    assert isinstance(instance, PaymentSystemService)


def test_bcol_factory_for_public(session, public_user_mock):
    """Test payment system creation for BCOL payment instances."""
    from pay_api.factory.payment_system_factory import PaymentSystemFactory  # noqa I001; errors out the test case

    instance = PaymentSystemFactory.create(payment_method="DRAWDOWN")
    assert isinstance(instance, BcolService)
    assert isinstance(instance, PaymentSystemService)


def test_bcol_factory_for_system(session, system_user_mock):
    """Test payment system creation for BCOL payment instances."""
    from pay_api.factory.payment_system_factory import PaymentSystemFactory  # noqa I001; errors out the test case

    # Try a DRAWDOWN for system user
    instance = PaymentSystemFactory.create(payment_method="DRAWDOWN")
    assert isinstance(instance, BcolService)

    # Create with not specifying a payment_method
    instance = PaymentSystemFactory.create(account_info={"bcolAccountNumber": "10000"})
    assert isinstance(instance, BcolService)


def test_pad_factory_for_system_fails(session, system_user_mock):
    """Test payment system creation for PAD payment instances."""
    from pay_api.exceptions import BusinessException
    from pay_api.factory.payment_system_factory import PaymentSystemFactory  # noqa I001; errors out the test case

    pad_account = PaymentAccountService.create(get_unlinked_pad_account_payload())
    # Try a DRAWDOWN for system user

    with pytest.raises(BusinessException) as excinfo:
        PaymentSystemFactory.create(payment_method="PAD", payment_account=pad_account)
    assert excinfo.value.code == Error.ACCOUNT_IN_PAD_CONFIRMATION_PERIOD.name

    time_delay = current_app.config["PAD_CONFIRMATION_PERIOD_IN_DAYS"]
    with freeze_time(datetime.now(tz=UTC) + timedelta(days=time_delay + 1, minutes=1)):
        instance = PaymentSystemFactory.create(payment_method="PAD", payment_account=pad_account)
        assert isinstance(instance, PadService)


def test_invalid_pay_system(session, public_user_mock):
    """Test invalid data."""
    from pay_api.exceptions import BusinessException
    from pay_api.factory.payment_system_factory import PaymentSystemFactory  # noqa I001; errors out the test case

    with pytest.raises(BusinessException) as excinfo:
        PaymentSystemFactory.create(payment_method=None, corp_type=None)
    assert excinfo.value.code == Error.INVALID_CORP_OR_FILING_TYPE.name

    with pytest.raises(BusinessException) as excinfo:
        PaymentSystemFactory.create(payment_method="XXX", corp_type="XXX")
    assert excinfo.value.code == Error.INVALID_CORP_OR_FILING_TYPE.name
