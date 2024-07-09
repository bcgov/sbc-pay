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
"""Test suite for payment reconciliation integration."""

from datetime import datetime

from pay_api.models import CfsAccount, Invoice, InvoiceReference, Payment, PaymentAccount
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus, PaymentSystem


def factory_payment_account(payment_system_code: str = 'PAYBC', payment_method_code: str = 'CC', account_number='4101',
                            bcol_user_id='test',
                            auth_account_id: str = '1234'):
    """Return Factory."""
    # Create a payment account
    account = PaymentAccount(
        auth_account_id=auth_account_id,
        bcol_user_id=bcol_user_id,
        bcol_account='TEST'
    ).save()

    CfsAccount(cfs_party='11111',
               cfs_account=account_number,
               cfs_site='29921', payment_account=account,
               pamynet_method_code=payment_method_code).save()

    if payment_system_code == PaymentSystem.BCOL.value:
        account.payment_method = PaymentMethod.DRAWDOWN.value
    elif payment_system_code == PaymentSystem.PAYBC.value:
        account.payment_method = payment_method_code

    return account


def factory_payment(
        payment_system_code: str = 'PAYBC', payment_method_code: str = 'CC',
        payment_status_code: str = PaymentStatus.CREATED.value,
        created_on: datetime = datetime.now(),
        invoice_number: str = None
):
    """Return Factory."""
    return Payment(
        payment_system_code=payment_system_code,
        payment_method_code=payment_method_code,
        payment_status_code=payment_status_code,
        invoice_number=invoice_number
    ).save()


def factory_invoice(payment_account, status_code: str = InvoiceStatus.CREATED.value,
                    corp_type_code='CP',
                    business_identifier: str = 'CP0001234',
                    service_fees: float = 0.0, total=0,
                    payment_method_code: str = PaymentMethod.DIRECT_PAY.value,
                    created_on: datetime = datetime.now(),
                    disbursement_status_code=None):
    """Return Factory."""
    return Invoice(
        invoice_status_code=status_code,
        payment_account_id=payment_account.id,
        total=total,
        created_by='test',
        created_on=created_on,
        business_identifier=business_identifier,
        corp_type_code=corp_type_code,
        folio_number='1234567890',
        service_fees=service_fees,
        bcol_account=payment_account.bcol_account,
        payment_method_code=payment_method_code,
        disbursement_status_code=disbursement_status_code
    ).save()


def factory_invoice_reference(invoice_id: int, invoice_number: str = '10021'):
    """Return Factory."""
    return InvoiceReference(invoice_id=invoice_id,
                            status_code=InvoiceReferenceStatus.ACTIVE.value,
                            invoice_number=invoice_number).save()
