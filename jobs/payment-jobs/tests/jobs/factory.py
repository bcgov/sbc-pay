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
    BcolPaymentAccount, CreditPaymentAccount, DistributionCode, InternalPaymentAccount, Invoice, InvoiceReference,
    Payment, PaymentAccount, PaymentLineItem, StatementSettings)
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, LineItemStatus, PaymentStatus


def factory_premium_payment_account(bcol_user_id='PB25020', bcol_account_id='1234567890',
                                    auth_account_id='1234') -> BcolPaymentAccount:
    """Return Factory."""
    account = PaymentAccount(auth_account_id=auth_account_id).save()

    return BcolPaymentAccount(
        bcol_user_id=bcol_user_id,
        bcol_account_id=bcol_account_id,
        account_id=account.id
    ).save()


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
        payment_system_code: str = 'BCOL',
        payment_method_code: str = 'DRAWDOWN',
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
    ).save()


def factory_invoice(payment: Payment,
                    payment_account,
                    status_code: str = InvoiceStatus.CREATED.value,
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
