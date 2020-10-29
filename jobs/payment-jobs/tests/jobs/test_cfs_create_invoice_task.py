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

"""Tests to assure the CreateInvoiceTask.

Test-Suite to ensure that the CreateInvoiceTask is working as expected.
"""

from datetime import datetime, timedelta

from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Payment as PaymentModel
from pay_api.utils.enums import CfsAccountStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentStatus

from tasks.cfs_create_invoice_task import CreateInvoiceTask

from .factory import (
    factory_create_online_banking_account, factory_create_pad_account, factory_invoice, factory_payment_line_item)


def test_create_invoice(session):
    """Test create invoice."""
    CreateInvoiceTask.create_invoices()
    assert True


def test_create_pad_invoice_single_transaction(session):
    """Assert PAD invoices are created."""
    # Create an account and an invoice for the account
    account = factory_create_pad_account(auth_account_id='1', status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now() - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(payment_account=account, created_on=previous_day, total=10, payment_method_code=None)

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    assert invoice.invoice_status_code == InvoiceStatus.CREATED.value

    CreateInvoiceTask.create_invoices()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.\
        find_reference_by_invoice_id_and_status(invoice.id, InvoiceReferenceStatus.ACTIVE.value)
    payment: PaymentModel = PaymentModel.find_payment_for_invoice(invoice.id)

    assert inv_ref
    assert updated_invoice.invoice_status_code == InvoiceStatus.SETTLEMENT_SCHEDULED.value
    assert payment.payment_status_code == PaymentStatus.CREATED.value


def test_create_pad_invoice_multiple_transactions(session):
    """Assert PAD invoices are created."""
    # Create an account and an invoice for the account
    account = factory_create_pad_account(auth_account_id='1', status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now() - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(payment_account=account, created_on=previous_day, total=10, payment_method_code=None)
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    # Create another invoice for this account
    invoice2 = factory_invoice(payment_account=account, created_on=previous_day, total=10, payment_method_code=None)
    fee_schedule2 = FeeScheduleModel.find_by_filing_type_and_corp_type('CP', 'OTADD')
    line2 = factory_payment_line_item(invoice2.id, fee_schedule_id=fee_schedule2.fee_schedule_id)
    line2.save()

    CreateInvoiceTask.create_invoices()
    invoice2 = InvoiceModel.find_by_id(invoice2.id)
    invoice = InvoiceModel.find_by_id(invoice.id)
    assert invoice2.invoice_status_code == invoice.invoice_status_code == InvoiceStatus.SETTLEMENT_SCHEDULED.value

    # Find payment for this invoice and assert single payment is created for both invoices
    payment: PaymentModel = PaymentModel.find_payment_for_invoice(invoice.id)
    payment2: PaymentModel = PaymentModel.find_payment_for_invoice(invoice2.id)
    assert payment == payment2


def test_create_pad_invoice_before_cutoff(session):
    """Assert PAD invoices are created."""
    # Create an account and an invoice for the account
    account = factory_create_pad_account(auth_account_id='1', status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now() - timedelta(days=2)
    # Create an invoice for this account
    invoice = factory_invoice(payment_account=account, created_on=previous_day, total=10, payment_method_code=None)

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    assert invoice.invoice_status_code == InvoiceStatus.CREATED.value

    CreateInvoiceTask.create_invoices()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.\
        find_reference_by_invoice_id_and_status(invoice.id, InvoiceReferenceStatus.ACTIVE.value)
    payment: PaymentModel = PaymentModel.find_payment_for_invoice(invoice.id)

    assert inv_ref is None
    assert payment is None
    assert updated_invoice.invoice_status_code == InvoiceStatus.CREATED.value


def test_create_online_banking_transaction(session):
    """Assert Online Banking invoices are created."""
    # Create an account and an invoice for the account
    account = factory_create_online_banking_account(auth_account_id='1', status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now() - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(payment_account=account, created_on=previous_day, total=10, payment_method_code=None)

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type('CP', 'OTANN')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    assert invoice.invoice_status_code == InvoiceStatus.CREATED.value

    CreateInvoiceTask.create_invoices()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.\
        find_reference_by_invoice_id_and_status(invoice.id, InvoiceReferenceStatus.ACTIVE.value)
    payment: PaymentModel = PaymentModel.find_payment_for_invoice(invoice.id)

    assert inv_ref
    assert updated_invoice.invoice_status_code == InvoiceStatus.SETTLEMENT_SCHEDULED.value
    assert payment.payment_status_code == PaymentStatus.CREATED.value
