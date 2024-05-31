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

"""Tests to assure the EFT GL Transfer model.

Test-Suite to ensure that the EFT GL Transfer model is working as expected.
"""
from datetime import datetime

from pay_api.models.eft_gl_transfers import EFTGLTransfer as EFTGLTransferModel
from pay_api.models.eft_short_names import EFTShortnames as EFTShortnamesModel
from pay_api.utils.enums import EFTGlTransferType, EFTShortnameStatus
from tests.utilities.base_test import factory_invoice, factory_payment, factory_payment_account


def create_invoice_data():
    """Create invoice seed data for test."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account=payment_account)
    invoice.save()
    assert invoice.id is not None

    return invoice


def create_short_name_data():
    """Create shortname seed data for test."""
    eft_short_name = EFTShortnamesModel()
    eft_short_name.short_name = 'ABC'
    eft_short_name.status_code = EFTShortnameStatus.LINKED.value
    eft_short_name.save()

    return eft_short_name


def test_eft_gl_transfer_defaults(session):
    """Assert eft gl transfer defaults are stored."""
    eft_shortname = create_short_name_data()
    eft_gl_transfer = EFTGLTransferModel()
    eft_gl_transfer.transfer_amount = 125.00
    eft_gl_transfer.transfer_type = EFTGlTransferType.TRANSFER.value
    eft_gl_transfer.source_gl = 'test source gl'
    eft_gl_transfer.target_gl = 'test target gl'
    eft_gl_transfer.short_name_id = eft_shortname.id
    eft_gl_transfer.save()

    assert eft_gl_transfer.id is not None
    eft_gl_transfer = EFTGLTransferModel.find_by_id(eft_gl_transfer.id)

    today = datetime.now().date()
    assert eft_gl_transfer.created_on.date() == today
    assert eft_gl_transfer.invoice_id is None
    assert eft_gl_transfer.is_processed is False
    assert eft_gl_transfer.processed_on is None
    assert eft_gl_transfer.short_name_id == eft_shortname.id
    assert eft_gl_transfer.source_gl == 'test source gl'
    assert eft_gl_transfer.target_gl == 'test target gl'
    assert eft_gl_transfer.transfer_amount == 125.00
    assert eft_gl_transfer.transfer_type == EFTGlTransferType.TRANSFER.value
    assert eft_gl_transfer.transfer_date.date() == today


def test_eft_gl_transfer_all_attributes(session):
    """Assert all eft file attributes are stored."""
    invoice = create_invoice_data()
    eft_shortname = create_short_name_data()
    eft_gl_transfer = EFTGLTransferModel()

    created_on = datetime(2024, 1, 1, 10, 0, 0)
    transfer_date = datetime(2024, 1, 10, 8, 0)
    processed_on = datetime(2024, 1, 11, 8, 0)
    transfer_type = EFTGlTransferType.PAYMENT.value
    transfer_amount = 125.00

    eft_gl_transfer.created_on = created_on
    eft_gl_transfer.invoice_id = invoice.id
    eft_gl_transfer.is_processed = True
    eft_gl_transfer.processed_on = processed_on
    eft_gl_transfer.short_name_id = eft_shortname.id
    eft_gl_transfer.source_gl = 'test source gl'
    eft_gl_transfer.target_gl = 'test target gl'
    eft_gl_transfer.transfer_type = transfer_type
    eft_gl_transfer.transfer_date = transfer_date
    eft_gl_transfer.transfer_amount = transfer_amount
    eft_gl_transfer.save()

    assert eft_gl_transfer.id is not None
    eft_gl_transfer = EFTGLTransferModel.find_by_id(eft_gl_transfer.id)

    assert eft_gl_transfer.created_on == created_on
    assert eft_gl_transfer.invoice_id == invoice.id
    assert eft_gl_transfer.is_processed
    assert eft_gl_transfer.processed_on == processed_on
    assert eft_gl_transfer.short_name_id == eft_shortname.id
    assert eft_gl_transfer.source_gl == 'test source gl'
    assert eft_gl_transfer.target_gl == 'test target gl'
    assert eft_gl_transfer.transfer_type == EFTGlTransferType.PAYMENT.value
    assert eft_gl_transfer.transfer_date == transfer_date
    assert eft_gl_transfer.transfer_amount == transfer_amount
