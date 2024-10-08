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
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel

# from pay_api.models import Payment as PaymentModel
from pay_api.services import CFSService
from pay_api.utils.enums import CfsAccountStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod
from requests import Response
from requests.exceptions import HTTPError

from tasks.cfs_create_invoice_task import CreateInvoiceTask

from .factory import (
    factory_create_eft_account,
    factory_create_online_banking_account,
    factory_create_pad_account,
    factory_invoice,
    factory_payment_line_item,
    factory_routing_slip_account,
)


def test_create_invoice(session):
    """Test create invoice."""
    CreateInvoiceTask.create_invoices()
    assert True


def test_create_pad_invoice_single_transaction(session):
    """Assert PAD invoices are created."""
    # Create an account and an invoice for the account
    account = factory_create_pad_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now(tz=timezone.utc) - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=None,
    )

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    assert invoice.invoice_status_code == InvoiceStatus.APPROVED.value

    CreateInvoiceTask.create_invoices()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
        invoice.id, InvoiceReferenceStatus.ACTIVE.value
    )

    assert inv_ref
    assert updated_invoice.invoice_status_code == InvoiceStatus.APPROVED.value


def test_create_pad_invoice_mixed_pli_values(session):
    """Assert PAD invoices are created with total = 0, service fees > 0."""
    # Create an account and an invoice for the account
    account = factory_create_pad_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now(tz=timezone.utc) - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=1.5,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=None,
    )

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("PPR", "FSREG")
    dist_code = DistributionCodeModel.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    # We need a dist code, if we're charging service fees.
    dist_code.service_fee_distribution_code_id = 1
    dist_code.save()
    line = factory_payment_line_item(
        invoice.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        total=0,
        service_fees=1.5,
    )
    line.save()
    assert invoice.invoice_status_code == InvoiceStatus.APPROVED.value

    CreateInvoiceTask.create_invoices()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
        invoice.id, InvoiceReferenceStatus.ACTIVE.value
    )

    assert inv_ref
    assert updated_invoice.invoice_status_code == InvoiceStatus.APPROVED.value


def test_create_rs_invoice_single_transaction(session):
    """Assert PAD invoices are created."""
    # Create an account and an invoice for the account
    rs_number = "123"
    account = factory_routing_slip_account(number=rs_number, status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now(tz=timezone.utc) - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=PaymentMethod.INTERNAL.value,
        routing_slip=rs_number,
    )

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    invoice_data = {
        "invoice_number": "123",
        "pbc_ref_number": "10005",
        "party_number": "11111",
        "party_name": "invoice",
    }

    assert invoice.invoice_status_code == InvoiceStatus.APPROVED.value
    invoice_failed_res = Response()
    invoice_failed_res.status_code = 400

    # Testing the flow where create_account_invoice already has an invoice.
    with patch.object(
        CFSService,
        "create_account_invoice",
        return_value=invoice_failed_res,
        side_effect=HTTPError(),
    ) as mock_create_invoice:
        with patch.object(CFSService, "get_invoice", return_value=invoice_data) as mock_get_invoice:
            CreateInvoiceTask.create_invoices()
            mock_create_invoice.assert_called()
            mock_get_invoice.assert_called()

    # Regular flow where create_account_invoice succeeds.
    with patch.object(CFSService, "create_account_invoice", return_value=invoice_data) as mock_create_invoice:
        CreateInvoiceTask.create_invoices()
        mock_create_invoice.assert_called()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
        invoice.id, InvoiceReferenceStatus.COMPLETED.value
    )

    assert inv_ref
    assert updated_invoice.invoice_status_code == InvoiceStatus.PAID.value


def test_create_pad_invoice_single_transaction_run_again(session):
    """Assert PAD invoices are created."""
    # Create an account and an invoice for the account
    account = factory_create_pad_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now(tz=timezone.utc) - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=None,
    )

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    invoice_response = {
        "invoice_number": "10021",
        "pbc_ref_number": "10005",
        "party_number": "11111",
        "party_name": "invoice",
    }
    assert invoice.invoice_status_code == InvoiceStatus.APPROVED.value

    with patch.object(CFSService, "create_account_invoice", return_value=invoice_response) as mock_cfs:
        CreateInvoiceTask.create_invoices()
        mock_cfs.assert_called()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
        invoice.id, InvoiceReferenceStatus.ACTIVE.value
    )

    assert inv_ref
    assert updated_invoice.invoice_status_code == InvoiceStatus.APPROVED.value

    with patch.object(CFSService, "create_account_invoice", return_value=invoice_response) as mock_cfs:
        CreateInvoiceTask.create_invoices()
        mock_cfs.assert_not_called()


def test_create_pad_invoice_for_frozen_accounts(session):
    """Assert PAD invoices are created."""
    # Create an account and an invoice for the account
    account = factory_create_pad_account(auth_account_id="1", status=CfsAccountStatus.FREEZE.value)
    previous_day = datetime.now(tz=timezone.utc) - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=None,
    )

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    assert invoice.invoice_status_code == InvoiceStatus.APPROVED.value

    CreateInvoiceTask.create_invoices()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
        invoice.id, InvoiceReferenceStatus.ACTIVE.value
    )

    assert inv_ref is None
    assert updated_invoice.invoice_status_code == InvoiceStatus.APPROVED.value


def test_create_pad_invoice_multiple_transactions(session):
    """Assert PAD invoices are created."""
    # Create an account and an invoice for the account
    account = factory_create_pad_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now(tz=timezone.utc) - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=None,
    )
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    # Create another invoice for this account
    invoice2 = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=None,
    )
    fee_schedule2 = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTADD")
    line2 = factory_payment_line_item(invoice2.id, fee_schedule_id=fee_schedule2.fee_schedule_id)
    line2.save()

    CreateInvoiceTask.create_invoices()
    invoice2 = InvoiceModel.find_by_id(invoice2.id)
    invoice = InvoiceModel.find_by_id(invoice.id)
    assert invoice2.invoice_status_code == invoice.invoice_status_code == InvoiceStatus.APPROVED.value


def test_create_pad_invoice_before_cutoff(session):
    """Assert PAD invoices are created."""
    # Create an account and an invoice for the account
    account = factory_create_pad_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now(tz=timezone.utc) - timedelta(days=2)
    # Create an invoice for this account
    invoice = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=None,
    )

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    assert invoice.invoice_status_code == InvoiceStatus.APPROVED.value

    CreateInvoiceTask.create_invoices()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
        invoice.id, InvoiceReferenceStatus.ACTIVE.value
    )

    assert inv_ref is not None  # As PAD will be summed up for all outstanding invoices
    assert updated_invoice.invoice_status_code == InvoiceStatus.APPROVED.value


def test_create_online_banking_transaction(session):
    """Assert Online Banking invoices are created."""
    # Create an account and an invoice for the account
    account = factory_create_online_banking_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now(tz=timezone.utc) - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        payment_method_code=None,
    )

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    assert invoice.invoice_status_code == InvoiceStatus.CREATED.value

    CreateInvoiceTask.create_invoices()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
        invoice.id, InvoiceReferenceStatus.ACTIVE.value
    )

    assert inv_ref
    assert updated_invoice.invoice_status_code == InvoiceStatus.SETTLEMENT_SCHEDULED.value


def test_create_eft_invoice(session):
    """Assert EFT invoice is created."""
    account = factory_create_eft_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now(tz=timezone.utc) - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=PaymentMethod.EFT.value,
    )

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    assert invoice.invoice_status_code == InvoiceStatus.APPROVED.value

    CreateInvoiceTask.create_invoices()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    invoice_reference: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
        invoice.id, InvoiceReferenceStatus.ACTIVE.value
    )

    assert invoice_reference
    assert updated_invoice.invoice_status_code == InvoiceStatus.APPROVED.value


def test_create_eft_invoice_rerun(session):
    """Assert EFT invoice is created."""
    account = factory_create_eft_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now(tz=timezone.utc) - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=PaymentMethod.EFT.value,
    )

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    invoice_response = {
        "invoice_number": "10021",
        "pbc_ref_number": "10005",
        "party_number": "11111",
        "party_name": "invoice",
    }
    assert invoice.invoice_status_code == InvoiceStatus.APPROVED.value

    with patch.object(CFSService, "create_account_invoice", return_value=invoice_response) as mock_cfs:
        CreateInvoiceTask.create_invoices()
        mock_cfs.assert_called()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
        invoice.id, InvoiceReferenceStatus.ACTIVE.value
    )

    assert inv_ref
    assert updated_invoice.invoice_status_code == InvoiceStatus.APPROVED.value

    with patch.object(CFSService, "create_account_invoice", return_value=invoice_response) as mock_cfs:
        CreateInvoiceTask.create_invoices()
        mock_cfs.assert_not_called()


def test_create_eft_invoice_on_frozen_account(session):
    """Assert EFT invoice is created."""
    account = factory_create_eft_account(auth_account_id="1", status=CfsAccountStatus.FREEZE.value)
    previous_day = datetime.now(tz=timezone.utc) - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=PaymentMethod.EFT.value,
    )

    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    assert invoice.invoice_status_code == InvoiceStatus.APPROVED.value

    CreateInvoiceTask.create_invoices()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
        invoice.id, InvoiceReferenceStatus.ACTIVE.value
    )

    assert inv_ref is None
    assert updated_invoice.invoice_status_code == InvoiceStatus.APPROVED.value


def test_create_eft_invoices(session):
    """Assert EFT invoices are created."""
    account = factory_create_eft_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now(tz=timezone.utc) - timedelta(days=1)
    # Create an invoice for this account
    invoice = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=PaymentMethod.EFT.value,
    )
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    # Create another invoice for this account
    invoice2 = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=PaymentMethod.EFT.value,
    )
    fee_schedule2 = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTADD")
    line2 = factory_payment_line_item(invoice2.id, fee_schedule_id=fee_schedule2.fee_schedule_id)
    line2.save()

    CreateInvoiceTask.create_invoices()
    invoice2 = InvoiceModel.find_by_id(invoice2.id)
    invoice = InvoiceModel.find_by_id(invoice.id)
    assert invoice2.invoice_status_code == invoice.invoice_status_code == InvoiceStatus.APPROVED.value


def test_create_eft_invoice_before_cutoff(session):
    """Assert EFT invoices are created."""
    account = factory_create_eft_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    previous_day = datetime.now(tz=timezone.utc) - timedelta(days=2)
    # Create an invoice for this account
    invoice = factory_invoice(
        payment_account=account,
        created_on=previous_day,
        total=10,
        status_code=InvoiceStatus.APPROVED.value,
        payment_method_code=PaymentMethod.EFT.value,
    )
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("CP", "OTANN")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    assert invoice.invoice_status_code == InvoiceStatus.APPROVED.value

    CreateInvoiceTask.create_invoices()

    updated_invoice: InvoiceModel = InvoiceModel.find_by_id(invoice.id)
    inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
        invoice.id, InvoiceReferenceStatus.ACTIVE.value
    )

    assert inv_ref is not None  # As EFT will be summed up for all outstanding invoices
    assert updated_invoice.invoice_status_code == InvoiceStatus.APPROVED.value
