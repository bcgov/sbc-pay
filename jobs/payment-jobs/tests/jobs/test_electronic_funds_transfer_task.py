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

"""Tests to assure the CreateAccountTask.

Test-Suite to ensure that the CreateAccountTask for electronic funds transfer is working as expected.
"""
from datetime import datetime
from unittest.mock import patch

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import EFTShortnameLinks as EFTShortnameLinksModel
from pay_api.models import EFTShortnames as EFTShortnameModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.utils.enums import (
    CfsAccountStatus, EFTShortnameStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod)
from pay_api.services import CFSService
from tasks.eft_task import ElectronicFundsTransferTask

from .factory import (
    factory_create_eft_account, factory_create_eft_credit, factory_create_eft_credit_invoice_link,
    factory_create_eft_file, factory_create_eft_shortname, factory_create_eft_transaction, factory_eft_shortname_link,
    factory_invoice, factory_invoice_reference, factory_payment, factory_payment_line_item, factory_receipt)


def test_link_electronic_funds_transfers(session):
    """Test link electronic funds transfers."""
    auth_account_id = '1234'
    short_name = 'TEST1'

    payment_account = factory_create_eft_account(auth_account_id=auth_account_id, status=CfsAccountStatus.ACTIVE.value)
    eft_file = factory_create_eft_file()
    factory_create_eft_transaction(file_id=eft_file.id)
    eft_short_name = factory_create_eft_shortname(short_name=short_name)
    eft_short_name_link = factory_eft_shortname_link(
        short_name_id=eft_short_name.id,
        auth_account_id=auth_account_id,
        updated_by='test'
    ).save()
    invoice = factory_invoice(payment_account=payment_account, payment_method_code=PaymentMethod.EFT.value)
    factory_invoice_reference(invoice_id=invoice.id)
    factory_payment(payment_account_id=payment_account.id, payment_method_code=PaymentMethod.EFT.value,
                    invoice_amount=351.50)
    factory_create_eft_credit(
        amount=100, remaining_amount=0, eft_file_id=eft_file.id, short_name_id=eft_short_name.id,
        payment_account_id=payment_account.id)
    factory_create_eft_credit_invoice_link(invoice_id=invoice.id)

    eft_short_name = EFTShortnameModel.find_by_short_name(short_name)
    eft_short_name_link = EFTShortnameLinksModel.find_by_short_name_id(eft_short_name.id)[0]
    eft_short_name_link.updated_by = 'test'
    eft_short_name_link.updated_by_name = 'test'
    eft_short_name_link.updated_on = datetime.now()
    eft_short_name.save()

    payment_account: PaymentAccountModel = PaymentAccountModel.find_by_auth_account_id(
        eft_short_name_link.auth_account_id)

    cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_payment_method(
        payment_account.id, PaymentMethod.EFT.value)

    with patch('pay_api.services.CFSService.create_cfs_receipt') as mock_create_cfs:
        with patch.object(CFSService, 'get_receipt') as mock_get_receipt:
            ElectronicFundsTransferTask.link_electronic_funds_transfers_cfs()
            mock_create_cfs.assert_called()
            mock_get_receipt.assert_called()

    cfs_account: CfsAccountModel = CfsAccountModel.find_by_id(cfs_account.id)
    assert cfs_account.status == CfsAccountStatus.ACTIVE.value


def test_unlink_electronic_funds_transfers(session):
    """Test unlink electronic funds transfers."""
    auth_account_id = '1234'
    short_name = 'TEST1'
    receipt_number = '1111R'
    invoice_number = '1234'

    payment_account = factory_create_eft_account(auth_account_id=auth_account_id, status=CfsAccountStatus.ACTIVE.value)
    eft_file = factory_create_eft_file()
    eft_transaction = factory_create_eft_transaction(file_id=eft_file.id)
    eft_short_name = factory_create_eft_shortname(short_name=short_name)
    eft_short_name_link = factory_eft_shortname_link(
        short_name_id=eft_short_name.id,
        auth_account_id=auth_account_id,
        updated_by='test',
        status_code=EFTShortnameStatus.UNLINKED.value
    ).save()

    invoice = factory_invoice(payment_account=payment_account, total=30,
                              status_code=InvoiceStatus.PAID.value,
                              payment_method_code=PaymentMethod.EFT.value)

    factory_payment(payment_account_id=payment_account.id, payment_method_code=PaymentMethod.EFT.value,
                    invoice_amount=351.50, invoice_number=invoice_number)
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type('CP', 'OTANN')
    factory_payment_line_item(invoice_id=invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    factory_invoice_reference(invoice_id=invoice.id, status_code=InvoiceReferenceStatus.COMPLETED.value,
                              invoice_number=invoice_number)
    factory_create_eft_credit(
        amount=100, remaining_amount=0, eft_file_id=eft_file.id, short_name_id=eft_short_name.id,
        payment_account_id=payment_account.id,
        eft_transaction_id=eft_transaction.id)

    factory_receipt(invoice.id, receipt_number)

    eft_short_name = EFTShortnameModel.find_by_short_name(short_name)
    eft_short_name_link = EFTShortnameLinksModel.find_by_short_name_id(eft_short_name.id)[0]
    eft_short_name_link.updated_by = None
    eft_short_name_link.updated_by_name = None
    eft_short_name_link.updated_on = None
    eft_short_name.save()

    session.commit()

    with patch('pay_api.services.CFSService.reverse_rs_receipt_in_cfs') as mock_reverse:
        with patch('pay_api.services.CFSService.create_cfs_receipt') as mock_create_receipt:
            ElectronicFundsTransferTask.reverse_electronic_funds_transfers_cfs()
            mock_reverse.assert_called()
            mock_create_receipt.assert_called()
