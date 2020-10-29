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

"""A helper test.

Test-Suite to ensure that the /payments endpoint is working as expected.
"""

from datetime import datetime

from pay_api.models import (
    CfsAccount, DistributionCode, Invoice, InvoiceReference, Payment, PaymentAccount, PaymentLineItem,
    StatementSettings)
from pay_api.utils.enums import (
    CfsAccountStatus, InvoiceReferenceStatus, InvoiceStatus, LineItemStatus, PaymentMethod, PaymentStatus)


def factory_premium_payment_account(bcol_user_id='PB25020', bcol_account_id='1234567890', auth_account_id='1234'):
    """Return Factory."""
    account = PaymentAccount(auth_account_id=auth_account_id,
                             bcol_user_id=bcol_user_id,
                             bcol_account=bcol_account_id,
                             ).save()
    return account


def factory_statement_settings(pay_account_id: str, frequency='DAILY', from_date=datetime.now(),
                               to_date=None) -> StatementSettings:
    """Return Factory."""
    return StatementSettings(
        frequency=frequency,
        payment_account_id=pay_account_id,
        from_date=from_date,
        to_date=to_date
    ).save()


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
        created_on=created_on,
        invoice_number=invoice_number
    ).save()


def factory_invoice(payment_account, status_code: str = InvoiceStatus.CREATED.value,
                    corp_type_code='CP',
                    business_identifier: str = 'CP0001234',
                    service_fees: float = 0.0, total=0,
                    payment_method_code: str = PaymentMethod.DIRECT_PAY.value,
                    created_on: datetime = datetime.now()):
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
        payment_method_code=payment_method_code
    ).save()


def factory_payment_line_item(invoice_id: str, fee_schedule_id: int, filing_fees: int = 10, total: int = 10,
                              service_fees: int = 0, status: str = LineItemStatus.ACTIVE.value):
    """Return Factory."""
    return PaymentLineItem(
        invoice_id=invoice_id,
        fee_schedule_id=fee_schedule_id,
        filing_fees=filing_fees,
        total=total,
        service_fees=service_fees,
        line_item_status_code=status,
        fee_distribution_id=DistributionCode.find_by_active_for_fee_schedule(fee_schedule_id).distribution_code_id
    ).save()


def factory_invoice_reference(invoice_id: int, invoice_number: str = '10021'):
    """Return Factory."""
    return InvoiceReference(invoice_id=invoice_id,
                            status_code=InvoiceReferenceStatus.ACTIVE.value,
                            invoice_number=invoice_number).save()


def factory_create_online_banking_account(auth_account_id='1234', status=CfsAccountStatus.PENDING.value):
    """Return Factory."""
    account = PaymentAccount(auth_account_id=auth_account_id,
                             payment_method=PaymentMethod.ONLINE_BANKING.value,
                             auth_account_name=f'Test {auth_account_id}').save()
    CfsAccount(status=status, account_id=account.id).save()
    return account


def factory_create_pad_account(auth_account_id='1234', bank_number='001', bank_branch='004', bank_account='1234567890',
                               status=CfsAccountStatus.PENDING.value):
    """Return Factory."""
    account = PaymentAccount(auth_account_id=auth_account_id,
                             payment_method=PaymentMethod.PAD.value,
                             auth_account_name=f'Test {auth_account_id}').save()
    CfsAccount(status=status, account_id=account.id, bank_number=bank_number,
               bank_branch_number=bank_branch, bank_account_number=bank_account).save()
    return account
