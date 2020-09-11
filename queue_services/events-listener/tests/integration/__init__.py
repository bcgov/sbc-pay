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
"""Test suite for the integrations to NATS Queue."""

from datetime import datetime

from pay_api.models import (
    BcolPaymentAccount, CreditPaymentAccount, InternalPaymentAccount, Invoice, Payment, PaymentAccount)
from pay_api.utils.enums import InvoiceStatus, PaymentMethod, PaymentStatus, PaymentSystem


def factory_payment_account(corp_number: str = 'CP0001234', corp_type_code: str = 'CP',
                            payment_system_code: str = 'PAYBC', payment_method_code: str = 'CC', account_number='4101',
                            bcol_user_id='test',
                            auth_account_id: str = '1234'):
    """Return Factory."""
    # Create a payment account
    account = PaymentAccount(auth_account_id=auth_account_id).save()

    if payment_system_code == PaymentSystem.BCOL.value:
        return BcolPaymentAccount(
            bcol_user_id=bcol_user_id,
            bcol_account_id='TEST',
            account_id=account.id,

        )
    elif payment_system_code == PaymentSystem.PAYBC.value:
        if payment_method_code == PaymentMethod.CC.value:
            return CreditPaymentAccount(
                corp_number=corp_number,
                corp_type_code=corp_type_code,
                paybc_party='11111',
                paybc_account=account_number,
                paybc_site='29921',
                account_id=account.id
            )
        elif payment_method_code == PaymentMethod.DIRECT_PAY.value:
            return CreditPaymentAccount(
                corp_number=corp_number,
                corp_type_code=corp_type_code,
                account_id=account.id
            )
    elif payment_system_code == PaymentSystem.INTERNAL.value:
        return InternalPaymentAccount(
            corp_number=corp_number,
            corp_type_code=corp_type_code,
            account_id=account.id
        )


def factory_premium_payment_account(bcol_user_id='PB25020', bcol_account_id='1234567890', auth_account_id='1234'):
    """Return Factory."""
    account = PaymentAccount(auth_account_id=auth_account_id).save()

    return BcolPaymentAccount(
        bcol_user_id=bcol_user_id,
        bcol_account_id=bcol_account_id,
        account_id=account.id
    )


def factory_payment(
        payment_system_code: str = 'PAYBC', payment_method_code: str = 'CC',
        payment_status_code: str = PaymentStatus.CREATED.value,
        created_on: datetime = datetime.now()
):
    """Return Factory."""
    return Payment(
        payment_system_code=payment_system_code,
        payment_method_code=payment_method_code,
        payment_status_code=payment_status_code,
        created_by='test',
        created_on=created_on,
    )


def factory_invoice(payment: Payment, payment_account, status_code: str = InvoiceStatus.CREATED.value,
                    corp_type_code='CP',
                    business_identifier: str = 'CP0001234',
                    service_fees: float = 0.0, total=0):
    """Return Factory."""
    bcol_account_id = None
    credit_account_id = None
    internal_account_id = None
    if isinstance(payment_account, BcolPaymentAccount):
        bcol_account_id = payment_account.id
    elif isinstance(payment_account, InternalPaymentAccount):
        internal_account_id = payment_account.id
    if isinstance(payment_account, CreditPaymentAccount):
        credit_account_id = payment_account.id

    return Invoice(
        payment_id=payment.id,
        invoice_status_code=status_code,
        bcol_account_id=bcol_account_id,
        credit_account_id=credit_account_id,
        internal_account_id=internal_account_id,
        total=total,
        created_by='test',
        created_on=datetime.now(),
        business_identifier=business_identifier,
        corp_type_code=corp_type_code,
        folio_number='1234567890',
        service_fees=service_fees
    )
