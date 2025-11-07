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

from datetime import UTC, datetime, timedelta
from random import randrange

from pay_api.models import (
    CfsAccount,
    DistributionCode,
    DistributionCodeLink,
    EFTCredit,
    EFTCreditInvoiceLink,
    EFTFile,
    EFTRefund,
    EFTShortnameLinks,
    EFTShortnames,
    EFTShortnamesHistorical,
    EFTTransaction,
    Invoice,
    InvoiceReference,
    Payment,
    PaymentAccount,
    PaymentLineItem,
    Receipt,
    Refund,
    RefundsPartial,
    RoutingSlip,
    Statement,
    StatementInvoices,
    StatementRecipients,
    StatementSettings,
)
from pay_api.utils.enums import (
    CfsAccountStatus,
    DisbursementStatus,
    EFTHistoricalTypes,
    EFTProcessStatus,
    EFTShortnameStatus,
    EFTShortnameType,
    InvoiceReferenceStatus,
    InvoiceStatus,
    LineItemStatus,
    PaymentMethod,
    PaymentStatus,
    PaymentSystem,
    RefundsPartialStatus,
    RefundStatus,
    RefundType,
    RoutingSlipStatus,
)


def factory_premium_payment_account(bcol_user_id="PB25020", bcol_account_id="1234567890", auth_account_id="1234"):
    """Return Factory."""
    account = PaymentAccount(
        auth_account_id=auth_account_id,
        bcol_user_id=bcol_user_id,
        bcol_account=bcol_account_id,
        payment_method=PaymentMethod.DRAWDOWN.value,
    ).save()
    return account


def factory_statement_recipient(
    auth_user_id: int,
    first_name: str,
    last_name: str,
    email: str,
    payment_account_id: int,
):
    """Return statement recipient model."""
    return StatementRecipients(
        auth_user_id=auth_user_id,
        firstname=first_name,
        lastname=last_name,
        email=email,
        payment_account_id=payment_account_id,
    ).save()


def factory_statement_invoices(statement_id: str, invoice_id: str):
    """Return Factory."""
    return StatementInvoices(statement_id=statement_id, invoice_id=invoice_id).save()


def factory_statement(
    frequency: str = "WEEKLY",
    payment_account_id: str = None,
    from_date: datetime = datetime.now(tz=UTC),
    to_date: datetime = datetime.now(tz=UTC),
    statement_settings_id: str = None,
    created_on: datetime = datetime.now(tz=UTC),
    payment_methods: str = PaymentMethod.EFT.value,
):
    """Return Factory."""
    return Statement(
        frequency=frequency,
        statement_settings_id=statement_settings_id,
        payment_account_id=payment_account_id,
        from_date=from_date,
        to_date=to_date,
        created_on=created_on,
        payment_methods=payment_methods,
    ).save()


def factory_statement_settings(
    pay_account_id: str,
    frequency="DAILY",
    from_date=datetime.now(tz=UTC),
    to_date=None,
) -> StatementSettings:
    """Return Factory."""
    return StatementSettings(
        frequency=frequency,
        payment_account_id=pay_account_id,
        from_date=from_date,
        to_date=to_date,
    ).save()


def factory_payment(
    payment_system_code: str = "PAYBC",
    payment_method_code: str = "CC",
    payment_status_code: str = PaymentStatus.CREATED.value,
    payment_date: datetime = datetime.now(tz=UTC),
    invoice_number: str = None,
    payment_account_id: int = None,
    invoice_amount: float = None,
):
    """Return Factory."""
    return Payment(
        payment_system_code=payment_system_code,
        payment_method_code=payment_method_code,
        payment_status_code=payment_status_code,
        payment_date=payment_date,
        invoice_number=invoice_number,
        payment_account_id=payment_account_id,
        invoice_amount=invoice_amount,
    ).save()


def factory_invoice(
    payment_account: PaymentAccount,
    status_code: str = InvoiceStatus.CREATED.value,
    corp_type_code="CP",
    business_identifier: str = "CP0001234",
    service_fees: float = 0.0,
    total=0,
    paid=0,
    payment_method_code: str = PaymentMethod.DIRECT_PAY.value,
    created_on: datetime = datetime.now(tz=UTC),
    cfs_account_id: int = 0,
    routing_slip=None,
    disbursement_status_code=None,
):
    """Return Factory."""
    status_code = InvoiceStatus.APPROVED.value if payment_method_code == PaymentMethod.PAD.value else status_code
    invoice = Invoice(
        invoice_status_code=status_code,
        payment_account_id=payment_account.id,
        total=total,
        paid=paid,
        created_by="test",
        created_on=created_on,
        business_identifier=business_identifier,
        corp_type_code=corp_type_code,
        folio_number="1234567890",
        service_fees=service_fees,
        bcol_account=payment_account.bcol_account,
        payment_method_code=payment_method_code or payment_account.payment_method,
        routing_slip=routing_slip,
        disbursement_status_code=disbursement_status_code,
        payment_date=None,
        refund_date=None,
    )
    if cfs_account_id != 0:
        invoice.cfs_account_id = cfs_account_id

    invoice.save()
    return invoice


def factory_payment_line_item(
    invoice_id: str,
    fee_schedule_id: int,
    filing_fees: int = 10,
    total: int = 10,
    service_fees: int = 0,
    service_fees_gst: float = 0,
    statutory_fees_gst: float = 0,
    status: str = LineItemStatus.ACTIVE.value,
    fee_dist_id=None,
):
    """Return Factory."""
    if not fee_dist_id:
        fee_dist_id = DistributionCode.find_by_active_for_fee_schedule(fee_schedule_id).distribution_code_id
    return PaymentLineItem(
        invoice_id=invoice_id,
        fee_schedule_id=fee_schedule_id,
        filing_fees=filing_fees,
        total=total,
        service_fees=service_fees,
        service_fees_gst=service_fees_gst,
        statutory_fees_gst=statutory_fees_gst,
        line_item_status_code=status,
        fee_distribution_id=fee_dist_id,
    ).save()


def factory_invoice_reference(
    invoice_id: int,
    invoice_number: str = "10021",
    status_code=InvoiceReferenceStatus.ACTIVE.value,
    is_consolidated=False,
):
    """Return Factory."""
    return InvoiceReference(
        invoice_id=invoice_id,
        status_code=status_code,
        invoice_number=invoice_number,
        is_consolidated=is_consolidated,
    ).save()


def factory_create_online_banking_account(
    auth_account_id="1234", status=CfsAccountStatus.PENDING.value, cfs_account="12356"
):
    """Return Factory."""
    account = PaymentAccount(
        auth_account_id=auth_account_id,
        payment_method=PaymentMethod.ONLINE_BANKING.value,
        name=f"Test {auth_account_id}",
    ).save()
    CfsAccount(
        status=status,
        account_id=account.id,
        cfs_account=cfs_account,
        payment_method=PaymentMethod.ONLINE_BANKING.value,
    ).save()
    return account


def factory_create_pad_account(
    auth_account_id="1234",
    bank_number="001",
    bank_branch="004",
    bank_account="1234567890",
    status=CfsAccountStatus.PENDING.value,
    payment_method=PaymentMethod.PAD.value,
    confirmation_period: int = 3,
):
    """Return Factory."""
    date_after_wait_period = datetime.now(tz=UTC) + timedelta(confirmation_period)
    account = PaymentAccount(
        auth_account_id=auth_account_id,
        payment_method=payment_method,
        pad_activation_date=date_after_wait_period,
        name=f"Test {auth_account_id}",
    ).save()
    CfsAccount(
        status=status,
        account_id=account.id,
        bank_number=bank_number,
        bank_branch_number=bank_branch,
        bank_account_number=bank_account,
        payment_method=PaymentMethod.PAD.value,
    ).save()
    return account


def factory_create_direct_pay_account(auth_account_id="1234", payment_method=PaymentMethod.DIRECT_PAY.value):
    """Return Factory."""
    account = PaymentAccount(
        auth_account_id=auth_account_id,
        payment_method=payment_method,
        name=f"Test {auth_account_id}",
    )
    return account


def factory_routing_slip_account(
    number: str = "1234",
    status: str = CfsAccountStatus.PENDING.value,
    total: int = 0,
    remaining_amount: int = 0,
    routing_slip_date=datetime.now(tz=UTC),
    payment_method=PaymentMethod.CASH.value,
    auth_account_id="1234",
    routing_slip_status=RoutingSlipStatus.ACTIVE.value,
    refund_amount=0,
):
    """Create routing slip and return payment account with it."""
    payment_account = PaymentAccount(payment_method=payment_method, name=f"Test {auth_account_id}")
    payment_account.save()

    rs = RoutingSlip(
        number=number,
        payment_account_id=payment_account.id,
        status=routing_slip_status,
        total=total,
        remaining_amount=remaining_amount,
        created_by="test",
        routing_slip_date=routing_slip_date,
        refund_amount=refund_amount,
    ).save()

    Payment(
        payment_system_code=PaymentSystem.FAS.value,
        payment_account_id=payment_account.id,
        payment_method_code=PaymentMethod.CASH.value,
        payment_status_code=PaymentStatus.COMPLETED.value,
        receipt_number=number,
        is_routing_slip=True,
        paid_amount=rs.total,
        created_by="TEST",
    )

    CfsAccount(
        status=status,
        account_id=payment_account.id,
        payment_method=PaymentMethod.INTERNAL.value,
    ).save()

    return payment_account


def factory_create_eft_account(auth_account_id="1234", status=CfsAccountStatus.PENDING.value):
    """Return Factory."""
    payment_account = PaymentAccount(
        auth_account_id=auth_account_id,
        payment_method=PaymentMethod.EFT.value,
        name=f"Test {auth_account_id}",
    ).save()
    CfsAccount(
        status=status,
        account_id=payment_account.id,
        payment_method=PaymentMethod.EFT.value,
    ).save()
    return payment_account


def factory_create_eft_shortname(short_name: str, short_name_type: str = EFTShortnameType.EFT.value):
    """Return Factory."""
    short_name = EFTShortnames(short_name=short_name, type=short_name_type).save()
    return short_name


def factory_eft_shortname_link(
    short_name_id: int,
    auth_account_id: str = "1234",
    updated_by: str = None,
    updated_on: datetime = datetime.now(tz=UTC),
    status_code: str = EFTShortnameStatus.LINKED.value,
):
    """Return an EFT short name link model."""
    return EFTShortnameLinks(
        eft_short_name_id=short_name_id,
        auth_account_id=auth_account_id,
        status_code=status_code,
        updated_by=updated_by,
        updated_by_name=updated_by,
        updated_on=updated_on,
    ).save()


def factory_create_eft_credit(amount=100, remaining_amount=0, eft_file_id=1, short_name_id=1, eft_transaction_id=1):
    """Return Factory."""
    eft_credit = EFTCredit(
        amount=amount,
        remaining_amount=remaining_amount,
        eft_file_id=eft_file_id,
        short_name_id=short_name_id,
        eft_transaction_id=eft_transaction_id,
    ).save()
    return eft_credit


def factory_create_eft_file(file_ref="test.txt", status_code=EFTProcessStatus.COMPLETED.value):
    """Return Factory."""
    eft_file = EFTFile(file_ref=file_ref, status_code=status_code).save()
    return eft_file


def factory_create_eft_transaction(
    file_id=1,
    line_number=1,
    line_type="T",
    status_code=EFTProcessStatus.COMPLETED.value,
):
    """Return Factory."""
    eft_transaction = EFTTransaction(
        file_id=file_id,
        line_number=line_number,
        line_type=line_type,
        status_code=status_code,
    ).save()
    return eft_transaction


def factory_create_eft_credit_invoice_link(
    invoice_id=1, eft_credit_id=1, status_code="PENDING", amount=10, link_group_id=1
):
    """Return Factory."""
    eft_credit_invoice_link = EFTCreditInvoiceLink(
        amount=amount,
        invoice_id=invoice_id,
        eft_credit_id=eft_credit_id,
        receipt_number="1234",
        status_code=status_code,
        link_group_id=link_group_id,
    ).save()
    return eft_credit_invoice_link


def factory_create_eft_shortname_historical(
    payment_account_id=1,
    related_group_link_id=1,
    short_name_id=1,
    statement_number=123,
    transaction_type=EFTHistoricalTypes.STATEMENT_PAID.value,
):
    """Return Factory."""
    eft_historical = EFTShortnamesHistorical(
        amount=100,
        created_by="TEST USER",
        credit_balance=100,
        hidden=True,
        is_processing=True,
        payment_account_id=payment_account_id,
        related_group_link_id=related_group_link_id,
        short_name_id=short_name_id,
        statement_number=statement_number,
        transaction_date=datetime.now(tz=UTC),
        transaction_type=transaction_type,
    ).save()
    return eft_historical


def factory_create_eft_refund(
    cas_supplier_number: str = "1234",
    cas_supplier_site: str = "123",
    comment: str = "Test Comment",
    refund_amount: float = 100.0,
    refund_email: str = "",
    short_name_id: int = 1,
    status: str = InvoiceStatus.APPROVED.value,
    disbursement_status_code: str = DisbursementStatus.ACKNOWLEDGED.value,
    refund_method: str = PaymentMethod.EFT.value,
    entity_name: str = "TEST",
    city: str = "Victoria",
    region: str = "BC",
    street: str = "655 Douglas St",
    country: str = "CA",
    postal_code: str = "V8V 0B6",
):
    """Return Factory."""
    eft_refund = EFTRefund(
        cas_supplier_number=cas_supplier_number,
        cas_supplier_site=cas_supplier_site,
        comment=comment,
        disbursement_status_code=disbursement_status_code,
        refund_amount=refund_amount,
        refund_email=refund_email,
        short_name_id=short_name_id,
        status=status,
        created_on=datetime.now(tz=UTC),
        refund_method=refund_method,
        entity_name=entity_name,
        street=street,
        postal_code=postal_code,
        country=country,
        city=city,
        region=region,
    )
    return eft_refund


def factory_create_account(
    auth_account_id: str = "1234",
    payment_method_code: str = PaymentMethod.DIRECT_PAY.value,
    status: str = CfsAccountStatus.PENDING.value,
    statement_notification_enabled: bool = True,
):
    """Return payment account model."""
    account = PaymentAccount(
        auth_account_id=auth_account_id,
        payment_method=payment_method_code,
        name=f"Test {auth_account_id}",
        statement_notification_enabled=statement_notification_enabled,
    ).save()
    CfsAccount(status=status, account_id=account.id, payment_method=payment_method_code).save()
    return account


def factory_create_ejv_account(
    auth_account_id="1234",
    client: str = "112",
    resp_centre: str = "11111",
    service_line: str = "11111",
    stob: str = "1111",
    project_code: str = "1111111",
):
    """Return Factory."""
    account = PaymentAccount(
        auth_account_id=auth_account_id,
        payment_method=PaymentMethod.EJV.value,
        name=f"Test {auth_account_id}",
    ).save()
    DistributionCode(
        name=account.name,
        client=client,
        responsibility_centre=resp_centre,
        service_line=service_line,
        stob=stob,
        project_code=project_code,
        account_id=account.id,
        start_date=datetime.now(tz=UTC).date(),
        created_by="test",
    ).save()
    return account


def factory_distribution(
    name: str,
    client: str = "111",
    reps_centre: str = "22222",
    service_line: str = "33333",
    stob: str = "4444",
    project_code: str = "5555555",
    service_fee_dist_id: int = None,
    disbursement_dist_id: int = None,
):
    """Return Factory."""
    return DistributionCode(
        name=name,
        client=client,
        responsibility_centre=reps_centre,
        service_line=service_line,
        stob=stob,
        project_code=project_code,
        service_fee_distribution_code_id=service_fee_dist_id,
        disbursement_distribution_code_id=disbursement_dist_id,
        start_date=datetime.now(tz=UTC).date(),
        created_by="test",
    ).save()


def factory_distribution_link(distribution_code_id: int, fee_schedule_id: int):
    """Return Factory."""
    return DistributionCodeLink(fee_schedule_id=fee_schedule_id, distribution_code_id=distribution_code_id).save()


def factory_receipt(
    invoice_id: int,
    receipt_number: str = "TEST1234567890",
    receipt_date: datetime = datetime.now(tz=UTC),
    receipt_amount: float = 10.0,
):
    """Return Factory."""
    return Receipt(
        invoice_id=invoice_id,
        receipt_number=receipt_number,
        receipt_date=receipt_date,
        receipt_amount=receipt_amount,
    )


def factory_refund(routing_slip_id: int, details={}, status=RefundStatus.APPROVAL_NOT_REQUIRED.value):
    """Return Factory."""
    return Refund(
        routing_slip_id=routing_slip_id,
        requested_date=datetime.now(tz=UTC),
        reason="TEST",
        requested_by="TEST",
        details=details,
        status=status,
        type=RefundType.ROUTING_SLIP.value if routing_slip_id else RefundType.INVOICE.value,
    ).save()


def factory_refund_invoice(invoice_id: int, details={}, status=RefundStatus.APPROVAL_NOT_REQUIRED.value):
    """Return Factory."""
    return Refund(
        invoice_id=invoice_id,
        requested_date=datetime.now(tz=UTC),
        reason="TEST",
        requested_by="TEST",
        details=details,
        status=status,
        type=RefundType.INVOICE.value,
    ).save()


def factory_refund_partial(
    payment_line_item_id: int,
    invoice_id: int,
    refund_id: int,
    refund_amount: float,
    refund_type: str,
    created_by="test",
    created_on: datetime = datetime.now(tz=UTC),
    status: str = RefundsPartialStatus.REFUND_REQUESTED.value,
):
    """Return Factory."""
    return RefundsPartial(
        invoice_id=invoice_id,
        refund_id=refund_id,
        payment_line_item_id=payment_line_item_id,
        refund_amount=refund_amount,
        refund_type=refund_type,
        created_by=created_by,
        created_on=created_on,
        status=status,
    ).save()


def factory_pad_account_payload(
    account_id: int = randrange(999999),
    bank_number: str = "001",
    transit_number="999",
    bank_account="1234567890",
):
    """Return a pad payment account object."""
    return {
        "accountId": account_id,
        "accountName": "Test Account",
        "paymentInfo": {
            "methodOfPayment": PaymentMethod.PAD.value,
            "billable": True,
            "bankTransitNumber": transit_number,
            "bankInstitutionNumber": bank_number,
            "bankAccountNumber": bank_account,
        },
    }


def factory_eft_account_payload(payment_method: str = PaymentMethod.EFT.value, account_id: int = randrange(999999)):
    """Return a premium eft enable payment account object."""
    return {
        "accountId": account_id,
        "accountName": "Test Account",
        "bcolAccountNumber": "2000000",
        "bcolUserId": "U100000",
        "eft_enable": False,
        "paymentInfo": {"methodOfPayment": payment_method, "billable": True},
    }
