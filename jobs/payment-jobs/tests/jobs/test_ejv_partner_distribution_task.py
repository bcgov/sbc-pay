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
from datetime import datetime, timedelta

import pytest
from flask import current_app
from freezegun import freeze_time
from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import DistributionCode, EjvFile, EjvHeader, EjvInvoiceLink, FeeSchedule, Invoice, db
from pay_api.utils.enums import CfsAccountStatus, DisbursementStatus, InvoiceStatus, PaymentMethod

from tasks.ejv_partner_distribution_task import EjvPartnerDistributionTask

from .factory import (
    factory_create_pad_account, factory_distribution, factory_distribution_link, factory_invoice,
    factory_invoice_reference, factory_payment, factory_payment_line_item, factory_receipt)


@pytest.mark.parametrize('client_code, batch_type', [('112', 'GA'), ('113', 'GI'), ('ABC', 'GI')])
def test_disbursement_for_partners(session, monkeypatch, client_code, batch_type):
    """Test disbursement for partners.

    Steps:
    1) Create GL codes to match GA batch type.
    2) Create paid invoices for these partners.
    3) Run the job and assert results.
    """
    monkeypatch.setattr('pysftp.Connection.put', lambda *args, **kwargs: None)
    corp_type1 = CorpTypeModel.find_by_code('VS')
    corp_type2 = CorpTypeModel.find_by_code('CP')

    pad_account1 = factory_create_pad_account(auth_account_id='1234',
                                              bank_number='001',
                                              bank_branch='004',
                                              bank_account='1234567890',
                                              status=CfsAccountStatus.ACTIVE.value,
                                              payment_method=PaymentMethod.PAD.value)

    pad_account2 = factory_create_pad_account(auth_account_id='5678',
                                              bank_number='002',
                                              bank_branch='005',
                                              bank_account='0987654321',
                                              status=CfsAccountStatus.ACTIVE.value,
                                              payment_method=PaymentMethod.PAD.value)

    disbursement_distribution1 = factory_distribution(name='VS Disbursement', client=client_code)
    disbursement_distribution2 = factory_distribution(name='CP Disbursement', client=client_code)

    service_fee_distribution = factory_distribution(name='VS Service Fee', client='112')
    fee_distribution1 = factory_distribution(
        name='VS Fee distribution', client='112', service_fee_dist_id=service_fee_distribution.distribution_code_id,
        disbursement_dist_id=disbursement_distribution1.distribution_code_id
    )
    fee_distribution2 = factory_distribution(
        name='CP Fee distribution', client='112', service_fee_dist_id=service_fee_distribution.distribution_code_id,
        disbursement_dist_id=disbursement_distribution2.distribution_code_id
    )

    fee_schedule1 = FeeSchedule.find_by_filing_type_and_corp_type(corp_type1.code, 'WILLNOTICE')
    fee_schedule2 = FeeSchedule.find_by_filing_type_and_corp_type(corp_type2.code, 'NOFEE')

    # Ensure the fee schedules exist
    assert fee_schedule1, f"Fee schedule not found for corp_type {corp_type1.code} and filing type 'WILLNOTICE'"
    assert fee_schedule2, f"Fee schedule not found for corp_type {corp_type2.code} and filing type 'WILLNOTICE'"

    factory_distribution_link(fee_distribution1.distribution_code_id, fee_schedule1.fee_schedule_id)
    factory_distribution_link(fee_distribution2.distribution_code_id, fee_schedule2.fee_schedule_id)

    invoice1 = factory_invoice(payment_account=pad_account1, corp_type_code=corp_type1.code, total=11.5,
                               status_code='PAID')
    invoice2 = factory_invoice(payment_account=pad_account1, corp_type_code=corp_type1.code, total=11.5,
                               status_code='PAID')
    invoice3 = factory_invoice(payment_account=pad_account2, corp_type_code=corp_type2.code, total=11.5,
                               status_code='PAID')

    factory_payment_line_item(invoice_id=invoice1.id,
                              fee_schedule_id=fee_schedule1.fee_schedule_id,
                              filing_fees=10,
                              total=10,
                              service_fees=1.5,
                              fee_dist_id=fee_distribution1.distribution_code_id)
    factory_payment_line_item(invoice_id=invoice2.id,
                              fee_schedule_id=fee_schedule1.fee_schedule_id,
                              filing_fees=10,
                              total=10,
                              service_fees=1.5,
                              fee_dist_id=fee_distribution1.distribution_code_id)
    factory_payment_line_item(invoice_id=invoice3.id,
                              fee_schedule_id=fee_schedule2.fee_schedule_id,
                              filing_fees=10,
                              total=10,
                              service_fees=1.5,
                              fee_dist_id=fee_distribution2.distribution_code_id)

    inv_ref1 = factory_invoice_reference(invoice_id=invoice1.id)
    inv_ref2 = factory_invoice_reference(invoice_id=invoice2.id)
    inv_ref3 = factory_invoice_reference(invoice_id=invoice3.id)
    factory_payment(invoice_number=inv_ref1.invoice_number, payment_status_code='COMPLETED')
    factory_payment(invoice_number=inv_ref2.invoice_number, payment_status_code='COMPLETED')
    factory_payment(invoice_number=inv_ref3.invoice_number, payment_status_code='COMPLETED')
    factory_receipt(invoice_id=invoice1.id, receipt_date=datetime.today()).save()
    factory_receipt(invoice_id=invoice2.id, receipt_date=datetime.today()).save()
    factory_receipt(invoice_id=invoice3.id, receipt_date=datetime.today()).save()

    EjvPartnerDistributionTask.create_ejv_file()

    # Lookup invoices and assert disbursement status
    invoice1 = Invoice.find_by_id(invoice1.id)
    invoice2 = Invoice.find_by_id(invoice2.id)
    invoice3 = Invoice.find_by_id(invoice3.id)
    assert invoice1.disbursement_status_code is None
    assert invoice2.disbursement_status_code is None
    assert invoice3.disbursement_status_code is None

    day_after_time_delay = datetime.today() + timedelta(days=(current_app.config.get('DISBURSEMENT_DELAY_IN_DAYS') + 1))
    with freeze_time(day_after_time_delay):
        EjvPartnerDistributionTask.create_ejv_file()
        # Lookup invoices and assert disbursement status
        invoice1 = Invoice.find_by_id(invoice1.id)
        invoice2 = Invoice.find_by_id(invoice2.id)
        invoice3 = Invoice.find_by_id(invoice3.id)
        assert invoice1.disbursement_status_code == DisbursementStatus.UPLOADED.value
        assert invoice2.disbursement_status_code == DisbursementStatus.UPLOADED.value
        assert invoice3.disbursement_status_code == DisbursementStatus.UPLOADED.value

        ejv_inv_link1 = db.session.query(EjvInvoiceLink).filter(EjvInvoiceLink.invoice_id == invoice1.id).first()
        ejv_inv_link2 = db.session.query(EjvInvoiceLink).filter(EjvInvoiceLink.invoice_id == invoice2.id).first()
        ejv_inv_link3 = db.session.query(EjvInvoiceLink).filter(EjvInvoiceLink.invoice_id == invoice3.id).first()
        assert ejv_inv_link1
        assert ejv_inv_link2
        assert ejv_inv_link3

        # Assert the sequence numbers are correctly assigned and reset for each partner
        assert ejv_inv_link1.sequence == 1
        assert ejv_inv_link2.sequence == 2
        assert ejv_inv_link3.sequence == 1  # Sequence reset for the second partner

        ejv_header1 = db.session.query(EjvHeader).filter(EjvHeader.id == ejv_inv_link1.ejv_header_id).first()
        ejv_header2 = db.session.query(EjvHeader).filter(EjvHeader.id == ejv_inv_link2.ejv_header_id).first()
        ejv_header3 = db.session.query(EjvHeader).filter(EjvHeader.id == ejv_inv_link3.ejv_header_id).first()
        assert ejv_header1.disbursement_status_code == DisbursementStatus.UPLOADED.value
        assert ejv_header2.disbursement_status_code == DisbursementStatus.UPLOADED.value
        assert ejv_header3.disbursement_status_code == DisbursementStatus.UPLOADED.value
        assert ejv_header1 == ejv_header2
        assert ejv_header1 != ejv_header3  # Different header for different partner

        ejv_file1 = EjvFile.find_by_id(ejv_header1.ejv_file_id)
        ejv_file2 = EjvFile.find_by_id(ejv_header3.ejv_file_id)
        assert ejv_file1
        assert ejv_file2
        assert ejv_file1.disbursement_status_code == DisbursementStatus.UPLOADED.value, f'{batch_type}'
        assert ejv_file2.disbursement_status_code == DisbursementStatus.UPLOADED.value, f'{batch_type}'

    # Reverse those payments and assert records.
    # Set the status of invoice as disbursement completed, so that reversal can kick start.
    invoice1.disbursement_status_code = DisbursementStatus.COMPLETED.value
    invoice2.disbursement_status_code = DisbursementStatus.COMPLETED.value
    invoice3.disbursement_status_code = DisbursementStatus.COMPLETED.value
    ejv_file1.disbursement_status_code = DisbursementStatus.COMPLETED.value
    ejv_file2.disbursement_status_code = DisbursementStatus.COMPLETED.value
    invoice1.invoice_status_code = InvoiceStatus.REFUNDED.value
    invoice2.invoice_status_code = InvoiceStatus.REFUNDED.value
    invoice3.invoice_status_code = InvoiceStatus.REFUNDED.value
    invoice1.refund_date = datetime.now()
    invoice2.refund_date = datetime.now()
    invoice3.refund_date = datetime.now()
    invoice1.save()
    invoice2.save()
    invoice3.save()

    EjvPartnerDistributionTask.create_ejv_file()
    # Lookup invoices and assert disbursement status
    invoice1 = Invoice.find_by_id(invoice1.id)
    invoice2 = Invoice.find_by_id(invoice2.id)
    invoice3 = Invoice.find_by_id(invoice3.id)
    assert invoice1.disbursement_status_code == DisbursementStatus.UPLOADED.value
    assert invoice2.disbursement_status_code == DisbursementStatus.UPLOADED.value
    assert invoice3.disbursement_status_code == DisbursementStatus.UPLOADED.value