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

from datetime import datetime, timedelta

from pay_api.models import (
    CfsAccount, DistributionCode, DistributionCodeLink, Invoice, InvoiceReference, Payment, PaymentAccount,
    PaymentLineItem, Receipt, Refund, RoutingSlip, StatementSettings)
from pay_api.utils.enums import (
    CfsAccountStatus, InvoiceReferenceStatus, InvoiceStatus, LineItemStatus, PaymentMethod, PaymentStatus,
    PaymentSystem, RoutingSlipStatus)


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
        payment_date: datetime = datetime.now(),
        invoice_number: str = None
):
    """Return Factory."""
    return Payment(
        payment_system_code=payment_system_code,
        payment_method_code=payment_method_code,
        payment_status_code=payment_status_code,
        payment_date=payment_date,
        invoice_number=invoice_number
    ).save()


def factory_invoice(payment_account: PaymentAccount, status_code: str = InvoiceStatus.CREATED.value,
                    corp_type_code='CP',
                    business_identifier: str = 'CP0001234',
                    service_fees: float = 0.0, total=0,
                    payment_method_code: str = PaymentMethod.DIRECT_PAY.value,
                    created_on: datetime = datetime.now(),
                    cfs_account_id: int = 0,
                    routing_slip=None
                    ):
    """Return Factory."""
    status_code = InvoiceStatus.APPROVED.value if payment_method_code == PaymentMethod.PAD.value else status_code
    invoice = Invoice(
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
        payment_method_code=payment_method_code or payment_account.payment_method,
        routing_slip=routing_slip

    )
    if cfs_account_id != 0:
        invoice.cfs_account_id = cfs_account_id

    invoice.save()
    return invoice


def factory_payment_line_item(invoice_id: str, fee_schedule_id: int, filing_fees: int = 10, total: int = 10,
                              service_fees: int = 0, status: str = LineItemStatus.ACTIVE.value,
                              fee_dist_id=None):
    """Return Factory."""
    if not fee_dist_id:
        fee_dist_id = DistributionCode.find_by_active_for_fee_schedule(fee_schedule_id).distribution_code_id
    return PaymentLineItem(
        invoice_id=invoice_id,
        fee_schedule_id=fee_schedule_id,
        filing_fees=filing_fees,
        total=total,
        service_fees=service_fees,
        line_item_status_code=status,
        fee_distribution_id=fee_dist_id
    ).save()


def factory_invoice_reference(invoice_id: int, invoice_number: str = '10021',
                              status_code=InvoiceReferenceStatus.ACTIVE.value):
    """Return Factory."""
    return InvoiceReference(invoice_id=invoice_id,
                            status_code=status_code,
                            invoice_number=invoice_number).save()


def factory_create_online_banking_account(auth_account_id='1234', status=CfsAccountStatus.PENDING.value,
                                          cfs_account='12356'):
    """Return Factory."""
    account = PaymentAccount(auth_account_id=auth_account_id,
                             payment_method=PaymentMethod.ONLINE_BANKING.value,
                             name=f'Test {auth_account_id}').save()
    CfsAccount(status=status, account_id=account.id, cfs_account=cfs_account).save()
    return account


def factory_create_pad_account(auth_account_id='1234', bank_number='001', bank_branch='004', bank_account='1234567890',
                               status=CfsAccountStatus.PENDING.value, payment_method=PaymentMethod.PAD.value,
                               confirmation_period: int = 3):
    """Return Factory."""
    date_after_wait_period = datetime.today() + timedelta(confirmation_period)
    account = PaymentAccount(auth_account_id=auth_account_id,
                             payment_method=payment_method,
                             pad_activation_date=date_after_wait_period,
                             name=f'Test {auth_account_id}').save()
    CfsAccount(status=status, account_id=account.id, bank_number=bank_number,
               bank_branch_number=bank_branch, bank_account_number=bank_account).save()
    return account


def factory_routing_slip_account(
        number: str = '1234',
        status: str = CfsAccountStatus.PENDING.value,
        total: int = 0,
        remaining_amount: int = 0,
        routing_slip_date=datetime.now(),
        payment_method=PaymentMethod.CASH.value,
        auth_account_id='1234',
        routing_slip_status=RoutingSlipStatus.ACTIVE.value,
        refund_amount=0
):
    """Create routing slip and return payment account with it."""
    payment_account = PaymentAccount(
        payment_method=payment_method,
        name=f'Test {auth_account_id}')
    payment_account.save()

    rs = RoutingSlip(
        number=number,
        payment_account_id=payment_account.id,
        status=routing_slip_status,
        total=total,
        remaining_amount=remaining_amount,
        created_by='test',
        routing_slip_date=routing_slip_date,
        refund_amount=refund_amount
    ).save()

    Payment(payment_system_code=PaymentSystem.FAS.value,
            payment_account_id=payment_account.id,
            payment_method_code=PaymentMethod.CASH.value,
            payment_status_code=PaymentStatus.COMPLETED.value,
            receipt_number=number,
            is_routing_slip=True,
            paid_amount=rs.total,
            created_by='TEST')

    CfsAccount(status=status, account_id=payment_account.id).save()

    return payment_account


def factory_create_eft_account(auth_account_id='1234', status=CfsAccountStatus.PENDING.value):
    """Return Factory."""
    account = PaymentAccount(auth_account_id=auth_account_id,
                             payment_method=PaymentMethod.EFT.value,
                             name=f'Test {auth_account_id}').save()
    CfsAccount(status=status, account_id=account.id).save()
    return account


def factory_create_ejv_account(auth_account_id='1234',
                               client: str = '112',
                               resp_centre: str = '11111',
                               service_line: str = '11111',
                               stob: str = '1111',
                               project_code: str = '1111111'):
    """Return Factory."""
    account = PaymentAccount(auth_account_id=auth_account_id,
                             payment_method=PaymentMethod.EJV.value,
                             name=f'Test {auth_account_id}').save()
    DistributionCode(name=account.name,
                     client=client,
                     responsibility_centre=resp_centre,
                     service_line=service_line,
                     stob=stob,
                     project_code=project_code,
                     account_id=account.id,
                     start_date=datetime.today().date(),
                     created_by='test').save()
    return account


def factory_create_wire_account(auth_account_id='1234', status=CfsAccountStatus.PENDING.value):
    """Return Factory."""
    account = PaymentAccount(auth_account_id=auth_account_id,
                             payment_method=PaymentMethod.WIRE.value,
                             name=f'Test {auth_account_id}').save()
    CfsAccount(status=status, account_id=account.id).save()
    return account


def factory_distribution(name: str, client: str = '111', reps_centre: str = '22222', service_line: str = '33333',
                         stob: str = '4444', project_code: str = '5555555', service_fee_dist_id: int = None,
                         disbursement_dist_id: int = None):
    """Return Factory."""
    return DistributionCode(name=name,
                            client=client,
                            responsibility_centre=reps_centre,
                            service_line=service_line,
                            stob=stob,
                            project_code=project_code,
                            service_fee_distribution_code_id=service_fee_dist_id,
                            disbursement_distribution_code_id=disbursement_dist_id,
                            start_date=datetime.today().date(),
                            created_by='test').save()


def factory_distribution_link(distribution_code_id: int, fee_schedule_id: int):
    """Return Factory."""
    return DistributionCodeLink(fee_schedule_id=fee_schedule_id,
                                distribution_code_id=distribution_code_id).save()


def factory_receipt(
        invoice_id: int,
        receipt_number: str = 'TEST1234567890',
        receipt_date: datetime = datetime.now(),
        receipt_amount: float = 10.0
):
    """Return Factory."""
    return Receipt(
        invoice_id=invoice_id,
        receipt_number=receipt_number,
        receipt_date=receipt_date,
        receipt_amount=receipt_amount
    )


def factory_refund(
        routing_slip_id: int,
        details={}
):
    """Return Factory."""
    return Refund(
        routing_slip_id=routing_slip_id,
        requested_date=datetime.now(),
        reason='TEST',
        requested_by='TEST',
        details=details
    ).save()
