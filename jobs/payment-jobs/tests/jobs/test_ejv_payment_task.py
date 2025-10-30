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

"""Tests to assure the CGI EJV Job.

Test-Suite to ensure that the CgiEjvJob is working as expected.
"""

from decimal import Decimal

from pay_api.models import (
    DistributionCode,
    EjvFile,
    EjvHeader,
    EjvLink,
    FeeSchedule,
    Invoice,
    InvoiceReference,
    RefundsPartial,
    db,
)
from pay_api.utils.enums import (
    DisbursementStatus,
    EjvFileType,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    RefundsPartialStatus,
    RefundsPartialType,
)
from tasks.ejv_payment_task import EjvPaymentTask

from .factory import (
    factory_create_ejv_account,
    factory_distribution,
    factory_invoice,
    factory_payment_line_item,
    factory_refund_invoice,
    factory_refund_partial,
)


def test_payments_for_gov_accounts(session, monkeypatch, google_bucket_mock):
    """Test payments for gov accounts.

    Steps:
    1) Update a distribution code with client code 112.
    2) Create multiple gov accounts for GA - 112
    3) Create multiple gov accounts for GI - NOT 112
    4) Create some transactions for these accounts
    5) Run the job and assert results.
    6) Test refund reversal for these payments
    7) Test partial refunds
    """
    monkeypatch.setattr("pysftp.Connection.put", lambda *_args, **_kwargs: None)

    corp_type = "BEN"
    filing_type = "BCINC"

    # Find fee schedule which have service fees.
    fee_schedule: FeeSchedule = FeeSchedule.find_by_filing_type_and_corp_type(corp_type, filing_type)
    # Create a service fee distribution code
    service_fee_dist_code = factory_distribution(
        name="service fee",
        client="112",
        reps_centre="99999",
        service_line="99999",
        stob="9999",
        project_code="9999999",
    )
    service_fee_dist_code.save()

    service_fee_gst_dist_code = factory_distribution(
        name="service fee gst",
        client="112",
        reps_centre="88888",
        service_line="88888",
        stob="8888",
        project_code="8888888",
    )
    service_fee_gst_dist_code.save()

    statutory_fees_gst_dist_code = factory_distribution(
        name="statutory fees gst",
        client="112",
        reps_centre="77777",
        service_line="77777",
        stob="7777",
        project_code="7777777",
    )
    statutory_fees_gst_dist_code.save()

    dist_code: DistributionCode = DistributionCode.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    dist_code.client = "112"
    dist_code.responsibility_centre = "22222"
    dist_code.service_line = "33333"
    dist_code.stob = "4444"
    dist_code.project_code = "5555555"
    dist_code.service_fee_distribution_code_id = service_fee_dist_code.distribution_code_id
    dist_code.service_fee_gst_distribution_code_id = service_fee_gst_dist_code.distribution_code_id
    dist_code.statutory_fees_gst_distribution_code_id = statutory_fees_gst_dist_code.distribution_code_id
    dist_code.save()

    # GA
    jv_account_1 = factory_create_ejv_account(auth_account_id="1")
    jv_account_2 = factory_create_ejv_account(auth_account_id="2")

    # GI
    jv_account_3 = factory_create_ejv_account(auth_account_id="3", client="111")
    jv_account_4 = factory_create_ejv_account(auth_account_id="4", client="111")

    jv_accounts = [jv_account_1, jv_account_2, jv_account_3, jv_account_4]
    inv_ids = []
    for jv_acc in jv_accounts:
        inv = factory_invoice(
            payment_account=jv_acc,
            corp_type_code=corp_type,
            total=101.5,
            status_code=InvoiceStatus.APPROVED.value,
            payment_method_code=None,
        )
        factory_payment_line_item(
            invoice_id=inv.id,
            fee_schedule_id=fee_schedule.fee_schedule_id,
            filing_fees=100,
            total=100,
            service_fees=1.5,
            service_fees_gst=0.2,
            statutory_fees_gst=5.0,
            fee_dist_id=dist_code.distribution_code_id,
        )
        inv_ids.append(inv.id)

    EjvPaymentTask.create_ejv_file()

    # Lookup invoice and assert invoice status
    for inv_id in inv_ids:
        invoice_ref = InvoiceReference.find_by_invoice_id_and_status(inv_id, InvoiceReferenceStatus.ACTIVE.value)
        assert invoice_ref

        ejv_inv_link: EjvLink = db.session.query(EjvLink).filter(EjvLink.link_id == inv_id).first()
        assert ejv_inv_link

        ejv_header = db.session.query(EjvHeader).filter(EjvHeader.id == ejv_inv_link.ejv_header_id).first()
        assert ejv_header.disbursement_status_code == DisbursementStatus.UPLOADED.value
        assert ejv_header

        ejv_file: EjvFile = EjvFile.find_by_id(ejv_header.ejv_file_id)
        assert ejv_file
        assert ejv_file.disbursement_status_code == DisbursementStatus.UPLOADED.value
        assert not ejv_file.file_type == EjvFileType.DISBURSEMENT.value

    # Update the disbursement_status_code to COMPLETED, so that we can create records for Reversals
    for ejv_file in db.session.query(EjvFile).all():
        ejv_file.disbursement_status_code = DisbursementStatus.COMPLETED.value
        ejv_file.save()

    # Try reversal on these payments.
    # Mark invoice as REFUND_REQUESTED and run a JV job again.
    for inv_id in inv_ids:
        # Set invoice ref status as COMPLETED, as that would be the status when the payment is reconciled.
        invoice_ref = InvoiceReference.find_by_invoice_id_and_status(inv_id, InvoiceReferenceStatus.ACTIVE.value)
        invoice_ref.status_code = InvoiceReferenceStatus.COMPLETED.value

        # Set invoice status for Refund requested.
        inv: Invoice = Invoice.find_by_id(inv_id)
        inv.invoice_status_code = InvoiceStatus.REFUND_REQUESTED.value
        inv.save()

    # Create a JV again, which should reverse the payments.
    EjvPaymentTask.create_ejv_file()

    # Lookup invoice and assert invoice status
    for inv_id in inv_ids:
        invoice_ref = InvoiceReference.find_by_invoice_id_and_status(inv_id, InvoiceReferenceStatus.ACTIVE.value)
        assert invoice_ref

        ejv_inv_link = (
            db.session.query(EjvLink)
            .filter(EjvLink.link_id == inv_id)
            .filter(EjvLink.disbursement_status_code == DisbursementStatus.UPLOADED.value)
            .first()
        )
        assert ejv_inv_link

        ejv_header = db.session.query(EjvHeader).filter(EjvHeader.id == ejv_inv_link.ejv_header_id).first()
        assert ejv_header

        ejv_file: EjvFile = EjvFile.find_by_id(ejv_header.ejv_file_id)
        assert ejv_file
        assert ejv_file.file_type == EjvFileType.PAYMENT.value

    # Now test partial refunds
    partial_refund_invoice = factory_invoice(
        payment_account=jv_account_1,
        corp_type_code=corp_type,
        total=200.0,
        status_code=InvoiceStatus.PAID.value,
        payment_method_code=PaymentMethod.EJV.value,
    )

    line_item = factory_payment_line_item(
        invoice_id=partial_refund_invoice.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        filing_fees=190.0,
        total=190.0,
        service_fees=10.0,
        service_fees_gst=1.3,
        statutory_fees_gst=8.7,
        fee_dist_id=dist_code.distribution_code_id,
    )

    refund = factory_refund_invoice(partial_refund_invoice.id)
    refund_partial = factory_refund_partial(
        invoice_id=partial_refund_invoice.id,
        refund_id=refund.id,
        payment_line_item_id=line_item.id,
        refund_amount=50.0,
        refund_type=RefundsPartialType.BASE_FEES.value,
        status=RefundsPartialStatus.REFUND_REQUESTED.value,
    )
    db.session.flush()

    refund_partials = RefundsPartial.get_partial_refunds_for_invoice(partial_refund_invoice.id)
    assert len(refund_partials) == 1
    assert refund_partials[0].id == refund_partial.id

    partial_refund_invoices = EjvPaymentTask.get_partial_refunds_invoices(jv_account_1.id)
    assert len(partial_refund_invoices) == 1
    assert partial_refund_invoices[0].id == partial_refund_invoice.id

    EjvPaymentTask.create_ejv_file()

    updated_refund_partial = RefundsPartial.find_by_id(refund_partial.id)
    assert updated_refund_partial.status == RefundsPartialStatus.REFUND_PROCESSING.value

    ejv_link = (
        db.session.query(EjvLink)
        .filter(EjvLink.link_id == refund_partial.id, EjvLink.link_type == "partial_refund")
        .first()
    )
    assert ejv_link is not None
    assert ejv_link.disbursement_status_code == DisbursementStatus.UPLOADED.value

    ejv_header = db.session.query(EjvHeader).filter(EjvHeader.id == ejv_link.ejv_header_id).first()
    assert ejv_header is not None
    assert ejv_header.disbursement_status_code == DisbursementStatus.UPLOADED.value

    ejv_file = EjvFile.find_by_id(ejv_header.ejv_file_id)
    assert ejv_file is not None
    assert ejv_file.disbursement_status_code == DisbursementStatus.UPLOADED.value
    assert ejv_file.file_type == EjvFileType.PAYMENT.value


def test_gst_transactions_creation(session, monkeypatch, google_bucket_mock):
    """Test that GST transactions are created when service_fees_gst and statutory_fees_gst are present."""
    monkeypatch.setattr("pysftp.Connection.put", lambda *_args, **_kwargs: None)

    corp_type = "BEN"
    filing_type = "BCINC"

    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type(corp_type, filing_type)

    service_fee_dist_code = factory_distribution(
        name="service fee",
        client="112",
        reps_centre="99999",
        service_line="99999",
        stob="9999",
        project_code="9999999",
    )
    service_fee_dist_code.save()

    service_fee_gst_dist_code = factory_distribution(
        name="service fee gst",
        client="112",
        reps_centre="88888",
        service_line="88888",
        stob="8888",
        project_code="8888888",
    )
    service_fee_gst_dist_code.save()

    statutory_fees_gst_dist_code = factory_distribution(
        name="statutory fees gst",
        client="112",
        reps_centre="77777",
        service_line="77777",
        stob="7777",
        project_code="7777777",
    )
    statutory_fees_gst_dist_code.save()

    dist_code = DistributionCode.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    dist_code.client = "112"
    dist_code.responsibility_centre = "22222"
    dist_code.service_line = "33333"
    dist_code.stob = "4444"
    dist_code.project_code = "5555555"
    dist_code.service_fee_distribution_code_id = service_fee_dist_code.distribution_code_id
    dist_code.service_fee_gst_distribution_code_id = service_fee_gst_dist_code.distribution_code_id
    dist_code.statutory_fees_gst_distribution_code_id = statutory_fees_gst_dist_code.distribution_code_id
    dist_code.save()

    jv_account = factory_create_ejv_account(auth_account_id="test_gst")

    inv = factory_invoice(
        payment_account=jv_account,
        corp_type_code=corp_type,
        total=110.7,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=None,
    )
    factory_payment_line_item(
        invoice_id=inv.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        filing_fees=100,
        total=100,
        service_fees=1.5,
        service_fees_gst=0.2,
        statutory_fees_gst=9.0,
        fee_dist_id=dist_code.distribution_code_id,
    )

    transactions = EjvPaymentTask._get_ejv_account_transactions(jv_account.id)

    assert len(transactions) == 4

    transaction_amounts = [t.line_item.amount for t in transactions]
    assert Decimal("100.00") in transaction_amounts
    assert Decimal("1.50") in transaction_amounts
    assert Decimal("0.20") in transaction_amounts
    assert Decimal("9.00") in transaction_amounts

    for transaction in transactions:
        if transaction.line_item.amount == Decimal("100.00"):
            assert transaction.line_distribution.distribution_code_id == dist_code.distribution_code_id
        elif transaction.line_item.amount == Decimal("1.50"):
            assert transaction.line_distribution.distribution_code_id == service_fee_dist_code.distribution_code_id
        elif transaction.line_item.amount == Decimal("0.20"):
            assert transaction.line_distribution.distribution_code_id == service_fee_gst_dist_code.distribution_code_id
        elif transaction.line_item.amount == Decimal("9.00"):
            assert (
                transaction.line_distribution.distribution_code_id == statutory_fees_gst_dist_code.distribution_code_id
            )
