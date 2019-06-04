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

from pay_api.models import PaymentAccount


def factory_payment_account(corp_number: str = 'CP1234', corp_type_code='CP', payment_system_code='PAYBC'):
    """Factory."""
    return PaymentAccount(corp_number=corp_number, corp_type_code=corp_type_code,
                          payment_system_code=payment_system_code)


def test_payment_account(session):
    """Assert a payment account is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment_account.save()

    assert payment_account.id is not None


def test_find_by_corp_number_and_corp_type_and_system(session):
    """Assert find works.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment_account.save()
    assert PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP1234', 'CP', 'PAYBC') is not None


def test_find_by_invalid_corp_number_and_corp_type_and_system(session):
    """Assert find works.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment_account.save()
    assert PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP1234', 'CP', 'BCOL') is None
    assert PaymentAccount.find_by_corp_number_and_corp_type_and_system(None, None, None) is None


def test_flush(session):
    """Assert flush works.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment_account.flush()
    assert PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP1234', 'CP', 'PAYBC') is not None
    payment_account.commit()
    assert PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP1234', 'CP', 'PAYBC') is not None


def test_rollback(session):
    """Assert rollback works.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment_account.flush()
    assert PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP1234', 'CP', 'PAYBC') is not None
    payment_account.rollback()
    assert PaymentAccount.find_by_corp_number_and_corp_type_and_system('CP1234', 'CP', 'PAYBC') is None
