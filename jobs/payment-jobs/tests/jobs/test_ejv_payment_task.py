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
from pay_api.models import DistributionCode, EjvFile, EjvHeader, EjvLink, FeeSchedule, Invoice, InvoiceReference, db
from pay_api.utils.enums import DisbursementStatus, EjvFileType, InvoiceReferenceStatus, InvoiceStatus

from tasks.ejv_payment_task import EjvPaymentTask

from .factory import factory_create_ejv_account, factory_distribution, factory_invoice, factory_payment_line_item


def test_payments_for_gov_accounts(session, monkeypatch):
    """Test payments for gov accounts.

    Steps:
    1) Update a distribution code with client code 112.
    2) Create multiple gov accounts for GA - 112
    3) Create multiple gov accounts for GI - NOT 112
    4) Create some transactions for these accounts
    5) Run the job and assert results.
    """
    monkeypatch.setattr('pysftp.Connection.put', lambda *args, **kwargs: None)

    corp_type = 'BEN'
    filing_type = 'BCINC'

    # Find fee schedule which have service fees.
    fee_schedule: FeeSchedule = FeeSchedule.find_by_filing_type_and_corp_type(corp_type, filing_type)
    # Create a service fee distribution code
    service_fee_dist_code = factory_distribution(name='service fee', client='112', reps_centre='99999',
                                                 service_line='99999',
                                                 stob='9999', project_code='9999999')
    service_fee_dist_code.save()

    dist_code: DistributionCode = DistributionCode.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    # Update fee dist code to match the requirement.
    dist_code.client = '112'
    dist_code.responsibility_centre = '22222'
    dist_code.service_line = '33333'
    dist_code.stob = '4444'
    dist_code.project_code = '5555555'
    dist_code.service_fee_distribution_code_id = service_fee_dist_code.distribution_code_id
    dist_code.save()

    # GA
    jv_account_1 = factory_create_ejv_account(auth_account_id='1')
    jv_account_2 = factory_create_ejv_account(auth_account_id='2')

    # GI
    jv_account_3 = factory_create_ejv_account(auth_account_id='3', client='111')
    jv_account_4 = factory_create_ejv_account(auth_account_id='4', client='111')

    jv_accounts = [jv_account_1, jv_account_2, jv_account_3, jv_account_4]
    inv_ids = []
    for jv_acc in jv_accounts:
        inv = factory_invoice(payment_account=jv_acc, corp_type_code=corp_type, total=101.5,
                              status_code=InvoiceStatus.APPROVED.value, payment_method_code=None)
        factory_payment_line_item(invoice_id=inv.id,
                                  fee_schedule_id=fee_schedule.fee_schedule_id,
                                  filing_fees=100,
                                  total=100,
                                  service_fees=1.5,
                                  fee_dist_id=dist_code.distribution_code_id)
        inv_ids.append(inv.id)

    EjvPaymentTask.create_ejv_file()

    # Lookup invoice and assert invoice status
    for inv_id in inv_ids:
        invoice_ref = InvoiceReference.find_by_invoice_id_and_status(inv_id,
                                                                     InvoiceReferenceStatus.ACTIVE.value)
        assert invoice_ref

        ejv_inv_link: EjvLink = db.session.query(EjvLink)\
            .filter(EjvLink.link_id == inv_id).first()
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
        invoice_ref = InvoiceReference.find_by_invoice_id_and_status(inv_id,
                                                                     InvoiceReferenceStatus.ACTIVE.value)
        invoice_ref.status_code = InvoiceReferenceStatus.COMPLETED.value

        # Set invoice status for Refund requested.
        inv: Invoice = Invoice.find_by_id(inv_id)
        inv.invoice_status_code = InvoiceStatus.REFUND_REQUESTED.value
        inv.save()

    # Create a JV again, which should reverse the payments.
    EjvPaymentTask.create_ejv_file()

    # Lookup invoice and assert invoice status
    for inv_id in inv_ids:
        invoice_ref = InvoiceReference.find_by_invoice_id_and_status(inv_id,
                                                                     InvoiceReferenceStatus.ACTIVE.value)
        assert invoice_ref

        ejv_inv_link = db.session.query(EjvLink).filter(EjvLink.link_id == inv_id)\
            .filter(EjvLink.disbursement_status_code == DisbursementStatus.UPLOADED.value).first()
        assert ejv_inv_link

        ejv_header = db.session.query(EjvHeader).filter(EjvHeader.id == ejv_inv_link.ejv_header_id).first()
        assert ejv_header

        ejv_file: EjvFile = EjvFile.find_by_id(ejv_header.ejv_file_id)
        assert ejv_file
        assert ejv_file.file_type == EjvFileType.PAYMENT.value
