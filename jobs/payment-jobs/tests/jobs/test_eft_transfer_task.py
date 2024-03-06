# Copyright © 2023 Province of British Columbia
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

"""Tests to assure the EFT CGI Transfer Job.

Test-Suite to ensure that the EFT Transfer task is working as expected.
"""
from datetime import datetime
from typing import List

import pytest
from flask import Flask
from pay_api.models import DistributionCode, EFTGLTransfer, EjvFile, EjvHeader, EjvLink, FeeSchedule, Invoice, db
from pay_api.utils.enums import DisbursementStatus, EFTGlTransferType, EjvFileType, InvoiceStatus, PaymentMethod

from tasks.eft_transfer_task import EftTransferTask

from .factory import (
    factory_create_eft_account, factory_create_eft_shortname, factory_distribution, factory_invoice,
    factory_payment_line_item)


def test_eft_transfer(app, session, monkeypatch):
    """Test EFT Holdings GL Transfer for EFT invoices.

    Steps:
    1) Create GL codes to match GA batch type.
    2) Create account to short name mappings
    3) Create paid invoices for EFT.
    4) Run the job and assert results.
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
    dist_code.responsibility_centre = '11111'
    dist_code.service_line = '22222'
    dist_code.stob = '3333'
    dist_code.project_code = '4444444'
    dist_code.service_fee_distribution_code_id = service_fee_dist_code.distribution_code_id
    dist_code.save()

    app.config['EFT_HOLDING_GL'] = '1128888888888888888000000000000000'
    eft_holding_gl = app.config['EFT_HOLDING_GL']
    distribution_gl = EftTransferTask.get_distribution_string(dist_code).strip()
    service_fee_gl = EftTransferTask.get_distribution_string(service_fee_dist_code).strip()

    # GA
    eft_account_1 = factory_create_eft_account(auth_account_id='1')
    eft_shortname_1 = factory_create_eft_shortname(auth_account_id='1', short_name='SHORTNAME1')
    eft_account_2 = factory_create_eft_account(auth_account_id='2')
    eft_shortname_2 = factory_create_eft_shortname(auth_account_id='2', short_name='SHORTNAME2')

    eft_accounts = [eft_account_1, eft_account_2]
    invoices: List[Invoice] = []
    for account in eft_accounts:
        inv = factory_invoice(payment_account=account, corp_type_code=corp_type, total=101.5,
                              status_code=InvoiceStatus.PAID.value, payment_method_code=PaymentMethod.EFT.value)
        factory_payment_line_item(invoice_id=inv.id,
                                  fee_schedule_id=fee_schedule.fee_schedule_id,
                                  filing_fees=100,
                                  total=100,
                                  service_fees=1.5,
                                  fee_dist_id=dist_code.distribution_code_id)
        invoices.append(inv)

    EftTransferTask.create_ejv_file()

    # Lookup invoice and assert disbursement status
    for invoice in invoices:
        ejv_inv_link: EjvLink = db.session.query(EjvLink) \
            .filter(EjvLink.link_id == invoice.id).first()
        assert ejv_inv_link

        ejv_header = db.session.query(EjvHeader).filter(EjvHeader.id == ejv_inv_link.ejv_header_id).first()
        assert ejv_header.disbursement_status_code == DisbursementStatus.UPLOADED.value
        assert ejv_header

        ejv_file: EjvFile = EjvFile.find_by_id(ejv_header.ejv_file_id)
        assert ejv_file
        assert ejv_file.disbursement_status_code == DisbursementStatus.UPLOADED.value
        assert ejv_file.file_type == EjvFileType.TRANSFER.value

    eft_transfers: List[EFTGLTransfer] = db.session.query(EFTGLTransfer).all()

    now = datetime.now().date()

    assert eft_transfers
    assert len(eft_transfers) == 4

    # Assert first short name line item distribution
    assert eft_transfers[0].id is not None
    assert eft_transfers[0].short_name_id == eft_shortname_1.id
    assert eft_transfers[0].invoice_id == invoices[0].id
    assert eft_transfers[0].transfer_amount == invoices[0].payment_line_items[0].total
    assert eft_transfers[0].transfer_type == EFTGlTransferType.TRANSFER.value
    assert eft_transfers[0].transfer_date.date() == now
    assert eft_transfers[0].is_processed
    assert eft_transfers[0].processed_on.date() == now
    assert eft_transfers[0].created_on.date() == now
    assert eft_transfers[0].source_gl == eft_holding_gl
    assert eft_transfers[0].target_gl == distribution_gl

    # Assert first short name service fee distribution
    assert eft_transfers[1].id is not None
    assert eft_transfers[1].short_name_id == eft_shortname_1.id
    assert eft_transfers[1].invoice_id == invoices[0].id
    assert eft_transfers[1].transfer_type == EFTGlTransferType.TRANSFER.value
    assert eft_transfers[1].transfer_amount == invoices[0].payment_line_items[0].service_fees
    assert eft_transfers[1].transfer_date.date() == now
    assert eft_transfers[1].is_processed
    assert eft_transfers[1].processed_on.date() == now
    assert eft_transfers[1].created_on.date() == now
    assert eft_transfers[1].source_gl == eft_holding_gl
    assert eft_transfers[1].target_gl == service_fee_gl

    # Assert second short name line item distribution
    assert eft_transfers[2].id is not None
    assert eft_transfers[2].short_name_id == eft_shortname_2.id
    assert eft_transfers[2].invoice_id == invoices[1].id
    assert eft_transfers[2].transfer_type == EFTGlTransferType.TRANSFER.value
    assert eft_transfers[2].transfer_amount == invoices[1].payment_line_items[0].total
    assert eft_transfers[2].transfer_date.date() == now
    assert eft_transfers[2].is_processed
    assert eft_transfers[2].processed_on.date() == now
    assert eft_transfers[2].created_on.date() == now
    assert eft_transfers[2].source_gl == eft_holding_gl
    assert eft_transfers[2].target_gl == distribution_gl

    # Assert second short name service fee distribution
    assert eft_transfers[3].id is not None
    assert eft_transfers[3].short_name_id == eft_shortname_2.id
    assert eft_transfers[3].invoice_id == invoices[1].id
    assert eft_transfers[3].transfer_type == EFTGlTransferType.TRANSFER.value
    assert eft_transfers[3].transfer_amount == invoices[1].payment_line_items[0].service_fees
    assert eft_transfers[3].transfer_date.date() == now
    assert eft_transfers[3].is_processed
    assert eft_transfers[3].processed_on.date() == now
    assert eft_transfers[3].created_on.date() == now
    assert eft_transfers[3].source_gl == eft_holding_gl
    assert eft_transfers[3].target_gl == service_fee_gl
