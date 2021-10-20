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
    corp_type: CorpTypeModel = CorpTypeModel.find_by_code('VS')

    pad_account = factory_create_pad_account(auth_account_id='1234',
                                             bank_number='001',
                                             bank_branch='004',
                                             bank_account='1234567890',
                                             status=CfsAccountStatus.ACTIVE.value,
                                             payment_method=PaymentMethod.PAD.value)

    # GI - Create 3 distribution code records. 1 for VS stat fee, 1 for service fee and 1 for disbursement.
    disbursement_distribution: DistributionCode = factory_distribution(name='VS Disbursement', client=client_code)

    service_fee_distribution: DistributionCode = factory_distribution(name='VS Service Fee', client='112')
    fee_distribution: DistributionCode = factory_distribution(
        name='VS Fee distribution', client='112', service_fee_dist_id=service_fee_distribution.distribution_code_id,
        disbursement_dist_id=disbursement_distribution.distribution_code_id
    )
    fee_schedule: FeeSchedule = FeeSchedule.find_by_filing_type_and_corp_type(corp_type.code, 'WILLNOTICE')

    factory_distribution_link(fee_distribution.distribution_code_id, fee_schedule.fee_schedule_id)
    invoice = factory_invoice(payment_account=pad_account, corp_type_code=corp_type.code, total=11.5,
                              status_code='PAID')

    factory_payment_line_item(invoice_id=invoice.id,
                              fee_schedule_id=fee_schedule.fee_schedule_id,
                              filing_fees=10,
                              total=10,
                              service_fees=1.5,
                              fee_dist_id=fee_distribution.distribution_code_id)

    inv_ref = factory_invoice_reference(invoice_id=invoice.id)
    factory_payment(invoice_number=inv_ref.invoice_number, payment_status_code='COMPLETED')
    factory_receipt(invoice_id=invoice.id, receipt_date=datetime.today()).save()

    EjvPartnerDistributionTask.create_ejv_file()

    # Lookup invoice and assert disbursement status
    invoice = Invoice.find_by_id(invoice.id)
    assert invoice.disbursement_status_code is None

    day_after_time_delay = datetime.today() + timedelta(days=(current_app.config.get('DISBURSEMENT_DELAY_IN_DAYS') + 1))
    with freeze_time(day_after_time_delay):
        EjvPartnerDistributionTask.create_ejv_file()
        # Lookup invoice and assert disbursement status
        invoice = Invoice.find_by_id(invoice.id)
        assert invoice.disbursement_status_code == DisbursementStatus.UPLOADED.value

        ejv_inv_link = db.session.query(EjvInvoiceLink).filter(EjvInvoiceLink.invoice_id == invoice.id).first()
        assert ejv_inv_link

        ejv_header = db.session.query(EjvHeader).filter(EjvHeader.id == ejv_inv_link.ejv_header_id).first()
        assert ejv_header.disbursement_status_code == DisbursementStatus.UPLOADED.value
        assert ejv_header

        ejv_file = EjvFile.find_by_id(ejv_header.ejv_file_id)
        assert ejv_file
        assert ejv_file.disbursement_status_code == DisbursementStatus.UPLOADED.value, f'{batch_type}'

    # Reverse those payments and assert records.
    # Set the status of invoice as disbursement completed, so that reversal can kick start.
    invoice.disbursement_status_code = DisbursementStatus.COMPLETED.value
    ejv_file.disbursement_status_code = DisbursementStatus.COMPLETED.value
    invoice.invoice_status_code = InvoiceStatus.REFUNDED.value
    invoice.save()

    EjvPartnerDistributionTask.create_ejv_file()
    # Lookup invoice and assert disbursement status
    invoice = Invoice.find_by_id(invoice.id)
    assert invoice.disbursement_status_code == DisbursementStatus.UPLOADED.value
