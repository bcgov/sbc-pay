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

"""Tests to assure the EFT GL Transfer service.

Test-Suite to ensure that the EFT GL Transfer service is working as expected.
"""
from datetime import datetime, timedelta

from _decimal import Decimal

from pay_api.models.eft_gl_transfers import EFTGLTransfer as EFTGLTransferModel
from pay_api.models.eft_short_names import EFTShortnames as EFTShortnamesModel
from pay_api.services.eft_gl_transfer import EFTGlTransfer, EFTGlTransferSearch
from pay_api.utils.enums import EFTGlTransferType
from tests.utilities.base_test import factory_invoice, factory_payment, factory_payment_account


def create_seed_transfer_data(short_name: str = 'ABC', invoice_id: int = None, transfer_amount: Decimal = 125.00):
    """Create EFT GL Transfer seed data."""
    eft_shortname = create_short_name_data(short_name)

    eft_gl_transfer = EFTGLTransferModel()
    eft_gl_transfer.transfer_type = EFTGlTransferType.TRANSFER.value
    eft_gl_transfer.transfer_amount = transfer_amount
    eft_gl_transfer.source_gl = 'test source gl'
    eft_gl_transfer.target_gl = 'test target gl'
    eft_gl_transfer.short_name_id = eft_shortname.id
    eft_gl_transfer.invoice_id = invoice_id
    eft_gl_transfer.save()

    return eft_shortname, eft_gl_transfer


def create_short_name_data(short_name: str):
    """Create EFT short name seed data."""
    eft_shortname = EFTShortnamesModel()
    eft_shortname.short_name = short_name
    eft_shortname.save()

    return eft_shortname


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


def assert_transfers(transfer_1: EFTGlTransfer, transfer_2: EFTGlTransfer):
    """Assert equality between two EFT GL Transfer models."""
    assert transfer_1.id == transfer_2.id
    assert transfer_1.created_on == transfer_2.created_on
    assert transfer_1.invoice_id == transfer_2.invoice_id
    assert transfer_1.is_processed == transfer_2.is_processed
    assert transfer_1.processed_on == transfer_2.processed_on
    assert transfer_1.short_name_id == transfer_2.short_name_id
    assert transfer_1.source_gl == transfer_2.source_gl
    assert transfer_1.target_gl == transfer_2.target_gl
    assert transfer_1.transfer_type == transfer_2.transfer_type
    assert transfer_1.transfer_date == transfer_2.transfer_date
    assert transfer_1.transfer_amount == transfer_2.transfer_amount


def test_find_by_transfer_id(session):
    """Test find by transfer id."""
    eft_shortname, eft_gl_transfer = create_seed_transfer_data()

    transfer = EFTGlTransfer.find_by_id(eft_gl_transfer.id)

    assert_transfers(transfer, eft_gl_transfer)


def test_find_by_short_name_id(session):
    """Test find by short_name_id."""
    eft_shortname, eft_gl_transfer = create_seed_transfer_data()

    # Assert find by short name returns the right record
    transfers = EFTGlTransfer.find_by_short_name_id(eft_shortname.id)
    assert transfers
    assert len(transfers) == 1
    assert_transfers(transfers[0], eft_gl_transfer)

    # Assert find by short name properly returns nothing
    transfers = EFTGlTransfer.find_by_short_name_id(9999)
    assert not transfers


def test_find_by_invoice_id(session):
    """Test find by invoice_id."""
    invoice = create_invoice_data()
    eft_shortname, eft_gl_transfer = create_seed_transfer_data(invoice_id=invoice.id)

    # Assert find by invoice returns the right record
    transfers = EFTGlTransfer.find_by_invoice_id(invoice.id)
    assert transfers
    assert len(transfers) == 1
    assert_transfers(transfers[0], eft_gl_transfer)

    # Assert find by invoice properly returns nothing
    transfers = EFTGlTransfer.find_by_invoice_id(9999)
    assert not transfers


def test_search_transfers(session):
    """Test EFT GL Transfers search."""
    # Confirm search all (no criteria) works
    transfers = EFTGlTransfer.search()
    assert not transfers

    # Create transfer data for testing the search
    invoice_1 = create_invoice_data()
    eft_shortname_1, eft_gl_transfer_1 = create_seed_transfer_data(short_name='ABC',
                                                                   invoice_id=invoice_1.id,
                                                                   transfer_amount=150.00)

    invoice_2 = create_invoice_data()
    eft_shortname_2, eft_gl_transfer_2 = create_seed_transfer_data(short_name='DEF',
                                                                   invoice_id=invoice_2.id,
                                                                   transfer_amount=300.25)
    eft_gl_transfer_2.is_processed = True
    eft_gl_transfer_2.processed_on = datetime.now()
    eft_gl_transfer_2.transfer_type = EFTGlTransferType.PAYMENT.value
    eft_gl_transfer_2.save()

    eft_shortname_3, eft_gl_transfer_3 = create_seed_transfer_data(short_name='GHI')

    transfers = EFTGlTransfer.search()
    assert transfers
    assert len(transfers) == 3

    assert_transfers(transfers[0], eft_gl_transfer_1)
    assert_transfers(transfers[1], eft_gl_transfer_2)
    assert_transfers(transfers[2], eft_gl_transfer_3)

    # Assert created_on search criteria
    transfers = EFTGlTransfer.search(EFTGlTransferSearch(created_on=datetime.now()))
    assert transfers
    assert len(transfers) == 3

    transfers = EFTGlTransfer.search(EFTGlTransferSearch(created_on=datetime.now() + timedelta(days=1)))
    assert not transfers

    # Assert invoice_id search criteria
    transfers = EFTGlTransfer.search(EFTGlTransferSearch(invoice_id=invoice_1.id))
    assert transfers
    assert len(transfers) == 1
    assert_transfers(transfers[0], eft_gl_transfer_1)

    # Assert is_processed True search criteria
    transfers = EFTGlTransfer.search(EFTGlTransferSearch(is_processed=True))
    assert transfers
    assert len(transfers) == 1
    assert_transfers(transfers[0], eft_gl_transfer_2)

    # Assert is_processed False search criteria
    transfers = EFTGlTransfer.search(EFTGlTransferSearch(is_processed=False))
    assert transfers
    assert len(transfers) == 2
    assert_transfers(transfers[0], eft_gl_transfer_1)
    assert_transfers(transfers[1], eft_gl_transfer_3)

    # Assert processed_on search criteria
    transfers = EFTGlTransfer.search(EFTGlTransferSearch(processed_on=datetime.now()))
    assert transfers
    assert len(transfers) == 1
    assert_transfers(transfers[0], eft_gl_transfer_2)

    transfers = EFTGlTransfer.search(EFTGlTransferSearch(processed_on=datetime.now() + timedelta(days=1)))
    assert not transfers

    # Assert short_name_id search criteria
    transfers = EFTGlTransfer.search(EFTGlTransferSearch(short_name_id=eft_shortname_3.id))
    assert transfers
    assert len(transfers) == 1
    assert_transfers(transfers[0], eft_gl_transfer_3)

    # Assert source_gl search criteria
    transfers = EFTGlTransfer.search(EFTGlTransferSearch(source_gl='test source gl'))
    assert transfers
    assert len(transfers) == 3

    transfers = EFTGlTransfer.search(EFTGlTransferSearch(source_gl='nothing'))
    assert not transfers

    # Assert target_gl search criteria
    transfers = EFTGlTransfer.search(EFTGlTransferSearch(target_gl='test target gl'))
    assert transfers
    assert len(transfers) == 3

    transfers = EFTGlTransfer.search(EFTGlTransferSearch(target_gl='nothing'))
    assert not transfers

    # Assert transfer_type search criteria
    transfers = EFTGlTransfer.search(EFTGlTransferSearch(transfer_type=EFTGlTransferType.TRANSFER.value))
    assert transfers
    assert len(transfers) == 2
    assert_transfers(transfers[0], eft_gl_transfer_1)
    assert_transfers(transfers[1], eft_gl_transfer_3)

    transfers = EFTGlTransfer.search(EFTGlTransferSearch(transfer_type=EFTGlTransferType.PAYMENT.value))
    assert transfers
    assert len(transfers) == 1
    assert_transfers(transfers[0], eft_gl_transfer_2)

    # Assert transfer date search criteria
    transfers = EFTGlTransfer.search(EFTGlTransferSearch(transfer_date=datetime.now()))
    assert transfers
    assert len(transfers) == 3

    transfers = EFTGlTransfer.search(EFTGlTransferSearch(transfer_date=datetime.now() + timedelta(days=1)))
    assert not transfers
