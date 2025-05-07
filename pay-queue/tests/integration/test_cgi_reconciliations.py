# Copyright © 2024 Province of British Columbia
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

"""Tests to assure the Payment Reconciliation.

Test-Suite to ensure that the Payment Reconciliation queue service is working as expected.
"""
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import EFTRefund as EFTRefundModel
from pay_api.models import EFTShortnames as EftShortNameModel
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import EjvLink as EjvLinkModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PartnerDisbursements as PartnerDisbursementsModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import Refund as RefundModel
from pay_api.models import RefundsPartial as RefundsPartialModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import db
from pay_api.utils.enums import (
    CfsAccountStatus,
    ChequeRefundStatus,
    DisbursementStatus,
    EFTShortnameRefundStatus,
    EFTShortnameType,
    EjvFileType,
    EJVLinkType,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    RefundsPartialStatus,
    RoutingSlipStatus,
)
from sbc_common_components.utils.enums import QueueMessageTypes
from sqlalchemy import text

from tests.integration.utils import add_file_event_to_queue_and_process

from .factory import (
    factory_create_eft_refund,
    factory_create_eft_shortname,
    factory_create_ejv_account,
    factory_create_pad_account,
    factory_distribution,
    factory_invoice,
    factory_invoice_reference,
    factory_payment_line_item,
    factory_refund,
    factory_routing_slip_account,
)
from .utils import upload_to_minio


def test_successful_partner_ejv_reconciliations(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = "1234"
    partner_code = "VS"
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type(
        corp_type_code=partner_code, filing_type_code="WILLSEARCH"
    )

    pay_account = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value, account_number=cfs_account_number)
    invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        corp_type_code="VS",
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
        status_code=InvoiceStatus.PAID.value,
    )
    eft_invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        corp_type_code="VS",
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.PAID.value,
    )
    invoice_id = invoice.id
    line_item = factory_payment_line_item(
        invoice_id=invoice.id,
        filing_fees=90.0,
        service_fees=10.0,
        total=90.0,
        fee_schedule_id=fee_schedule.fee_schedule_id,
    )
    dist_code = DistributionCodeModel.find_by_id(line_item.fee_distribution_id)
    # Check if the disbursement distribution is present for this.
    if not dist_code.disbursement_distribution_code_id:
        disbursement_distribution_code = factory_distribution(name="Disbursement")
        dist_code.disbursement_distribution_code_id = disbursement_distribution_code.distribution_code_id
        dist_code.save()

    invoice_number = "1234567890"
    factory_invoice_reference(
        invoice_id=invoice.id,
        invoice_number=invoice_number,
        status_code=InvoiceReferenceStatus.COMPLETED.value,
    )
    factory_invoice_reference(
        invoice_id=eft_invoice.id,
        invoice_number="1234567899",
        status_code=InvoiceReferenceStatus.COMPLETED.value,
    )
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()

    partner_disbursement = PartnerDisbursementsModel(
        amount=10,
        is_reversal=False,
        partner_code=eft_invoice.corp_type_code,
        status_code=DisbursementStatus.WAITING_FOR_JOB.value,
        target_id=eft_invoice.id,
        target_type=EJVLinkType.INVOICE.value,
    ).save()

    eft_flowthrough = f"{eft_invoice.id}-{partner_disbursement.id}"

    file_ref = f"INBOX.{datetime.now()}"
    ejv_file = EjvFileModel(file_ref=file_ref, disbursement_status_code=DisbursementStatus.UPLOADED.value).save()
    ejv_file_id = ejv_file.id

    ejv_header = EjvHeaderModel(
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
        ejv_file_id=ejv_file.id,
        partner_code=partner_code,
        payment_account_id=pay_account.id,
    ).save()
    ejv_header_id = ejv_header.id
    EjvLinkModel(
        link_id=invoice.id,
        link_type=EJVLinkType.INVOICE.value,
        ejv_header_id=ejv_header.id,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()

    EjvLinkModel(
        link_id=eft_invoice.id,
        link_type=EJVLinkType.INVOICE.value,
        ejv_header_id=ejv_header.id,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()

    ack_file_name = f"ACK.{file_ref}"

    with open(ack_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write("")
        jv_file.close()

    upload_to_minio(str.encode(""), ack_file_name)

    add_file_event_to_queue_and_process(client, ack_file_name, QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)

    # Now upload a feedback file and check the status.
    # Just create feedback file to mock the real feedback file.
    # Has legacy and added in PartnerDisbursements rows.
    feedback_content = (
        f"GABG...........00000000{ejv_file_id}...\n"
        f"..BH...0000................................................................................."
        f".....................................................................CGI\n"
        f"..JH...FI0000000{ejv_header_id}.........................000000000090.00....................."
        f"............................................................................................"
        f"............................................................................................"
        f".........0000..............................................................................."
        f".......................................................................CGI\n"
        f"..JD...FI0000000{ejv_header_id}0000120230529112............................................."
        f"...........000000000090.00D................................................................."
        f"..................................#{invoice_id}                                             "
        f"                                                                0000........................"
        f"............................................................................................"
        f"..................................CGI\n"
        f"..JD...FI0000000{ejv_header_id}0000220230529105............................................."
        f"...........000000000090.00C................................................................."
        f"..................................#{invoice_id}                                             "
        f"                                                                0000........................"
        f"............................................................................................"
        f"..................................CGI\n"
        f"..JD...FI0000000{ejv_header_id}0000120230529112............................................."
        f"...........000000000090.00D................................................................."
        f"..................................#{eft_flowthrough}                                        "
        f"                                                                0000........................"
        f"............................................................................................"
        f"..................................CGI\n"
        f"..JD...FI0000000{ejv_header_id}0000220230529105............................................."
        f"...........000000000090.00C................................................................."
        f"..................................#{eft_flowthrough}                                        "
        f"                                                                0000........................"
        f"............................................................................................"
        f"..................................CGI\n"
        f"..BT.......FI0000000{ejv_header_id}000000000000002000000000180.000000......................."
        f"............................................................................................"
        f"...................................CGI"
    )

    feedback_file_name = f"FEEDBACK.{file_ref}"

    with open(feedback_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    with open(feedback_file_name, "rb") as f:
        upload_to_minio(f.read(), feedback_file_name)

    add_file_event_to_queue_and_process(client, feedback_file_name, QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value)

    # Query EJV File and assert the status is changed
    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.COMPLETED.value
    invoice = InvoiceModel.find_by_id(invoice_id)
    assert invoice.disbursement_status_code == DisbursementStatus.COMPLETED.value
    assert partner_disbursement.status_code == DisbursementStatus.COMPLETED.value
    assert partner_disbursement.feedback_on
    assert partner_disbursement.processed_on


def test_failed_partner_ejv_reconciliations(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = "1234"
    partner_code = "VS"
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type(
        corp_type_code=partner_code, filing_type_code="WILLSEARCH"
    )

    pay_account = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value, account_number=cfs_account_number)
    invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        corp_type_code="VS",
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
        status_code=InvoiceStatus.PAID.value,
    )
    eft_invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        corp_type_code="VS",
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.PAID.value,
    )
    invoice_id = invoice.id
    line_item = factory_payment_line_item(
        invoice_id=invoice.id,
        filing_fees=90.0,
        service_fees=10.0,
        total=90.0,
        fee_schedule_id=fee_schedule.fee_schedule_id,
    )
    dist_code = DistributionCodeModel.find_by_id(line_item.fee_distribution_id)
    # Check if the disbursement distribution is present for this.
    if not dist_code.disbursement_distribution_code_id:
        disbursement_distribution_code = factory_distribution(name="Disbursement")
        dist_code.disbursement_distribution_code_id = disbursement_distribution_code.distribution_code_id
        dist_code.save()
    disbursement_distribution_code_id = dist_code.disbursement_distribution_code_id

    invoice_number = "1234567890"
    factory_invoice_reference(
        invoice_id=invoice.id,
        invoice_number=invoice_number,
        status_code=InvoiceReferenceStatus.COMPLETED.value,
    )
    factory_invoice_reference(
        invoice_id=eft_invoice.id,
        invoice_number="1234567899",
        status_code=InvoiceReferenceStatus.COMPLETED.value,
    )
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()

    partner_disbursement = PartnerDisbursementsModel(
        amount=10,
        is_reversal=False,
        partner_code=eft_invoice.corp_type_code,
        status_code=DisbursementStatus.WAITING_FOR_JOB.value,
        target_id=eft_invoice.id,
        target_type=EJVLinkType.INVOICE.value,
    ).save()

    eft_flowthrough = f"{eft_invoice.id}-{partner_disbursement.id}"

    file_ref = f"INBOX{datetime.now()}"
    ejv_file = EjvFileModel(file_ref=file_ref, disbursement_status_code=DisbursementStatus.UPLOADED.value).save()
    ejv_file_id = ejv_file.id

    ejv_header = EjvHeaderModel(
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
        ejv_file_id=ejv_file.id,
        partner_code=partner_code,
        payment_account_id=pay_account.id,
    ).save()
    ejv_header_id = ejv_header.id
    EjvLinkModel(
        link_id=invoice.id,
        link_type=EJVLinkType.INVOICE.value,
        ejv_header_id=ejv_header.id,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()

    EjvLinkModel(
        link_id=eft_invoice.id,
        link_type=EJVLinkType.INVOICE.value,
        ejv_header_id=ejv_header.id,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()

    ack_file_name = f"ACK.{file_ref}"

    with open(ack_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write("")
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    upload_to_minio(str.encode(""), ack_file_name)

    add_file_event_to_queue_and_process(client, ack_file_name, QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)

    # Now upload a feedback file and check the status.
    # Just create feedback file to mock the real feedback file.
    # Has legacy flow and PartnerDisbursements entries
    feedback_content = (
        f"GABG...........00000000{ejv_file_id}...\n"
        f"..BH...1111TESTERRORMESSAGE................................................................"
        f"......................................................................CGI\n"
        f"..JH...FI0000000{ejv_header_id}.........................000000000090.00...................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"............1111TESTERRORMESSAGE..........................................................."
        f"...........................................................................CGI\n"
        f"..JD...FI0000000{ejv_header_id}00001......................................................."
        f"............000000000090.00D..............................................................."
        f"....................................#{invoice_id}                                          "
        f"                                                                   1111TESTERRORMESSAGE...."
        f"..........................................................................................."
        f".......................................CGI\n"
        f"..JD...FI0000000{ejv_header_id}00002......................................................."
        f"............000000000090.00C..............................................................."
        f"....................................#{invoice_id}                                          "
        f"                                                                   1111TESTERRORMESSAGE...."
        f"..........................................................................................."
        f".......................................CGI\n"
        f"..JD...FI0000000{ejv_header_id}00001......................................................."
        f"............000000000090.00D..............................................................."
        f"....................................#{eft_flowthrough}                                     "
        f"                                                                      1111TESTERRORMESSAGE."
        f"..........................................................................................."
        f"..........................................CGI\n"
        f"..JD...FI0000000{ejv_header_id}00002......................................................."
        f"............000000000090.00C..............................................................."
        f"....................................#{eft_flowthrough}                                     "
        f"                                                                      1111TESTERRORMESSAGE."
        f"..........................................................................................."
        f"..........................................CGI\n"
        f"..BT...........FI0000000{ejv_header_id}000000000000002000000000180.001111TESTERRORMESSAGE.."
        f"..........................................................................................."
        f".........................................CGI\n"
    )

    feedback_file_name = f"FEEDBACK.{file_ref}"

    with open(feedback_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    with open(feedback_file_name, "rb") as f:
        upload_to_minio(f.read(), feedback_file_name)

    add_file_event_to_queue_and_process(client, feedback_file_name, QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value)

    # Query EJV File and assert the status is changed
    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.ERRORED.value
    invoice = InvoiceModel.find_by_id(invoice_id)
    assert invoice.disbursement_status_code == DisbursementStatus.ERRORED.value
    disbursement_distribution_code = DistributionCodeModel.find_by_id(disbursement_distribution_code_id)
    assert disbursement_distribution_code.stop_ejv
    assert partner_disbursement.status_code == DisbursementStatus.ERRORED.value
    assert partner_disbursement.processed_on


def test_successful_partner_reversal_ejv_reconciliations(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Mark the invoice as REFUNDED
    # 5. Assert that the payment to partner account is reversed.
    cfs_account_number = "1234"
    partner_code = "VS"
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type(
        corp_type_code=partner_code, filing_type_code="WILLSEARCH"
    )

    pay_account = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value, account_number=cfs_account_number)
    invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        corp_type_code="VS",
        payment_method_code=PaymentMethod.ONLINE_BANKING.value,
        status_code=InvoiceStatus.PAID.value,
    )
    eft_invoice = factory_invoice(
        payment_account=pay_account,
        total=100,
        service_fees=10.0,
        corp_type_code="VS",
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.PAID.value,
    )
    invoice_id = invoice.id
    line_item = factory_payment_line_item(
        invoice_id=invoice.id,
        filing_fees=90.0,
        service_fees=10.0,
        total=90.0,
        fee_schedule_id=fee_schedule.fee_schedule_id,
    )
    dist_code = DistributionCodeModel.find_by_id(line_item.fee_distribution_id)
    # Check if the disbursement distribution is present for this.
    if not dist_code.disbursement_distribution_code_id:
        disbursement_distribution_code = factory_distribution(name="Disbursement")
        dist_code.disbursement_distribution_code_id = disbursement_distribution_code.distribution_code_id
        dist_code.save()

    invoice_number = "1234567890"
    factory_invoice_reference(
        invoice_id=invoice.id,
        invoice_number=invoice_number,
        status_code=InvoiceReferenceStatus.COMPLETED.value,
    )
    factory_invoice_reference(
        invoice_id=eft_invoice.id,
        invoice_number="1234567899",
        status_code=InvoiceReferenceStatus.COMPLETED.value,
    )
    invoice.invoice_status_code = InvoiceStatus.REFUND_REQUESTED.value
    invoice.disbursement_status_code = DisbursementStatus.COMPLETED.value
    invoice = invoice.save()

    eft_invoice.invoice_status_code = InvoiceStatus.REFUND_REQUESTED.value
    eft_invoice.disbursement_status_code = DisbursementStatus.COMPLETED.value
    eft_invoice = eft_invoice.save()

    partner_disbursement = PartnerDisbursementsModel(
        amount=10,
        is_reversal=True,
        partner_code=eft_invoice.corp_type_code,
        status_code=DisbursementStatus.WAITING_FOR_JOB.value,
        target_id=eft_invoice.id,
        target_type=EJVLinkType.INVOICE.value,
    ).save()

    eft_flowthrough = f"{eft_invoice.id}-{partner_disbursement.id}"

    file_ref = f"INBOX.{datetime.now()}"
    ejv_file = EjvFileModel(file_ref=file_ref, disbursement_status_code=DisbursementStatus.UPLOADED.value).save()
    ejv_file_id = ejv_file.id

    ejv_header = EjvHeaderModel(
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
        ejv_file_id=ejv_file.id,
        partner_code=partner_code,
        payment_account_id=pay_account.id,
    ).save()
    ejv_header_id = ejv_header.id
    EjvLinkModel(
        link_id=invoice.id,
        link_type=EJVLinkType.INVOICE.value,
        ejv_header_id=ejv_header.id,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()

    EjvLinkModel(
        link_id=eft_invoice.id,
        link_type=EJVLinkType.INVOICE.value,
        ejv_header_id=ejv_header.id,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()

    ack_file_name = f"ACK.{file_ref}"

    with open(ack_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write("")
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    upload_to_minio(str.encode(""), ack_file_name)

    add_file_event_to_queue_and_process(client, ack_file_name, QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)

    # Now upload a feedback file and check the status.
    # Just create feedback file to mock the real feedback file.
    # Has legacy flow and PartnerDisbursements entries
    feedback_content = (
        f"GABG...........00000000{ejv_file_id}...\n"
        f"..BH...0000................................................................................."
        f".....................................................................CGI\n"
        f"..JH...FI0000000{ejv_header_id}.........................000000000090.00....................."
        f"............................................................................................"
        f"............................................................................................"
        f".........0000..............................................................................."
        f".......................................................................CGI\n"
        f"..JD...FI0000000{ejv_header_id}0000120230529112............................................."
        f"...........000000000090.00C................................................................."
        f"..................................#{invoice_id}                                             "
        f"                                                                0000........................"
        f"............................................................................................"
        f"..................................CGI\n"
        f"..JD...FI0000000{ejv_header_id}0000220230529105............................................."
        f"...........000000000090.00D................................................................."
        f"..................................#{invoice_id}                                             "
        f"                                                                0000........................"
        f"............................................................................................"
        f"..................................CGI\n"
        f"..JD...FI0000000{ejv_header_id}0000120230529112............................................."
        f"...........000000000090.00C................................................................."
        f"...................................{eft_flowthrough}                                        "
        f"                                                                0000........................"
        f"............................................................................................"
        f"..................................CGI\n"
        f"..JD...FI0000000{ejv_header_id}0000220230529105............................................."
        f"...........000000000090.00D................................................................."
        f"...................................{eft_flowthrough}                                        "
        f"                                                                0000........................"
        f"............................................................................................"
        f"..................................CGI\n"
        f"..BT.......FI0000000{ejv_header_id}000000000000002000000000180.000000......................."
        f"............................................................................................"
        f"...................................CGI"
    )

    feedback_file_name = f"FEEDBACK.{file_ref}"

    with open(feedback_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()

    with open(feedback_file_name, "rb") as f:
        upload_to_minio(f.read(), feedback_file_name)

    add_file_event_to_queue_and_process(client, feedback_file_name, QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.COMPLETED.value
    invoice = InvoiceModel.find_by_id(invoice_id)
    assert invoice.disbursement_status_code == DisbursementStatus.REVERSED.value
    assert invoice.disbursement_reversal_date == datetime(2023, 5, 29)
    assert partner_disbursement.status_code == DisbursementStatus.REVERSED.value
    assert partner_disbursement.feedback_on
    assert partner_disbursement.processed_on


def test_successful_payment_ejv_reconciliations(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create EJV payment accounts
    # 2. Create invoice and related records
    # 3. Create a feedback file and assert status
    corp_type = "BEN"
    filing_type = "BCINC"

    # Find fee schedule which have service fees.
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type(corp_type, filing_type)
    # Create a service fee distribution code
    service_fee_dist_code = factory_distribution(
        name="service fee",
        client="112",
        reps_centre="99999",
        service_line="99999",
        stob="9999",
        project_code="9999998",
    )
    service_fee_dist_code.save()

    dist_code = DistributionCodeModel.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    # Update fee dist code to match the requirement.
    dist_code.client = "112"
    dist_code.responsibility_centre = "22222"
    dist_code.service_line = "33333"
    dist_code.stob = "4444"
    dist_code.project_code = "5555559"
    dist_code.service_fee_distribution_code_id = service_fee_dist_code.distribution_code_id
    dist_code.save()

    # GA
    jv_account_1 = factory_create_ejv_account(auth_account_id="1")
    jv_account_2 = factory_create_ejv_account(auth_account_id="2")

    # GI
    jv_account_3 = factory_create_ejv_account(auth_account_id="3", client="111")
    jv_account_4 = factory_create_ejv_account(auth_account_id="4", client="111")

    # Now create JV records.
    # Create EJV File model
    file_ref = f"INBOX.{datetime.now()}"
    ejv_file = EjvFileModel(
        file_ref=file_ref,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
        file_type=EjvFileType.PAYMENT.value,
    ).save()
    ejv_file_id = ejv_file.id

    feedback_content = (
        f"GABG...........00000000{ejv_file_id}...\n"
        f"..BH...0000................................................................................."
        f".....................................................................CGI\n"
    )

    jv_accounts = [jv_account_1, jv_account_2, jv_account_3, jv_account_4]
    inv_ids = []
    jv_account_ids = []
    inv_total_amount = 101.5
    for jv_acc in jv_accounts:
        jv_account_ids.append(jv_acc.id)
        inv = factory_invoice(
            payment_account=jv_acc,
            corp_type_code=corp_type,
            total=inv_total_amount,
            status_code=InvoiceStatus.APPROVED.value,
            payment_method_code=None,
        )
        factory_invoice_reference(inv.id, status_code=InvoiceReferenceStatus.ACTIVE.value)
        line = factory_payment_line_item(
            invoice_id=inv.id,
            fee_schedule_id=fee_schedule.fee_schedule_id,
            filing_fees=100,
            total=100,
            service_fees=1.5,
            fee_dist_id=dist_code.distribution_code_id,
        )
        inv_ids.append(inv.id)
        ejv_header = EjvHeaderModel(
            disbursement_status_code=DisbursementStatus.UPLOADED.value,
            ejv_file_id=ejv_file.id,
            payment_account_id=jv_acc.id,
        ).save()

        EjvLinkModel(
            link_id=inv.id,
            link_type=EJVLinkType.INVOICE.value,
            ejv_header_id=ejv_header.id,
            disbursement_status_code=DisbursementStatus.UPLOADED.value,
        ).save()
        inv_total = f"{inv.total:.2f}".zfill(15)
        pay_line_amount = f"{line.total:.2f}".zfill(15)
        service_fee_amount = f"{line.service_fees:.2f}".zfill(15)
        # one JD has a shortened width (outside of spec).
        jh_and_jd = (
            f"..JH...FI0000000{ejv_header.id}.........................{inv_total}....................."
            f"............................................................................................"
            f"............................................................................................"
            f".........0000..............................................................................."
            f".......................................................................CGI\n"
            f"..JD...FI0000000{ejv_header.id}0000120230529................................................"
            f"...........{pay_line_amount}D................................................................."
            f"...................................{inv.id}                                             "
            f"                                                 0000........................"
            f"............................................................................................"
            f"..................................CGI\n"
            f"..JD...FI0000000{ejv_header.id}0000220230529................................................"
            f"...........{pay_line_amount}C................................................................."
            f"...................................{inv.id}                                             "
            f"                                                               0000........................"
            f"............................................................................................"
            f"..................................CGI\n"
            f"..JD...FI0000000{ejv_header.id}0000320230529..................................................."
            f"........{service_fee_amount}D................................................................."
            f"...................................{inv.id}                                             "
            f"                                                        0000........................"
            f"............................................................................................"
            f"..................................CGI\n"
            f"..JD...FI0000000{ejv_header.id}0000420230529................................................"
            f"...........{service_fee_amount}C.............................................................."
            f"......................................{inv.id}                                             "
            f"                                                                0000........................"
            f"............................................................................................"
            f"..................................CGI\n"
        )
        feedback_content = feedback_content + jh_and_jd
    feedback_content = (
        feedback_content + f"..BT.......FI0000000{ejv_header.id}000000000000002{inv_total}0000......."
        f"........................................................................."
        f"......................................................................CGI"
    )
    ack_file_name = f"ACK.{file_ref}"

    with open(ack_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write("")
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    upload_to_minio(str.encode(""), ack_file_name)

    add_file_event_to_queue_and_process(client, ack_file_name, QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)

    feedback_file_name = f"FEEDBACK.{file_ref}"

    with open(feedback_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    with open(feedback_file_name, "rb") as f:
        upload_to_minio(f.read(), feedback_file_name)

    add_file_event_to_queue_and_process(client, feedback_file_name, QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value)

    # Query EJV File and assert the status is changed
    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.COMPLETED.value
    # Assert invoice and receipt records
    for inv_id in inv_ids:
        invoice = InvoiceModel.find_by_id(inv_id)
        assert invoice.disbursement_status_code is None
        assert invoice.invoice_status_code == InvoiceStatus.PAID.value
        assert invoice.payment_date == datetime(2023, 5, 29)
        invoice_ref = InvoiceReferenceModel.find_by_invoice_id_and_status(
            inv_id, InvoiceReferenceStatus.COMPLETED.value
        )
        assert invoice_ref
        receipt = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice_id=inv_id)
        assert receipt

    # Assert payment records
    for jv_account_id in jv_account_ids:
        account = PaymentAccountModel.find_by_id(jv_account_id)
        payment = PaymentModel.search_account_payments(
            auth_account_id=account.auth_account_id,
            payment_status=PaymentStatus.COMPLETED.value,
            page=1,
            limit=100,
        )[0]
        assert len(payment) == 1
        assert payment[0][0].paid_amount == inv_total_amount


def test_successful_payment_reversal_ejv_reconciliations(session, app, client, mocker):
    """Test Reconciliations worker."""
    # 1. Create EJV payment accounts
    # 2. Create invoice and related records
    # 3. Create a feedback file and assert status
    corp_type = "CP"
    filing_type = "OTFDR"

    InvoiceModel.query.delete()
    # Reset the sequence, because the unit test is only dealing with 1 character for the invoice id.
    # This becomes more apparent when running unit tests in parallel.
    db.session.execute(text("ALTER SEQUENCE invoices_id_seq RESTART WITH 1"))
    db.session.commit()

    # Find fee schedule which have service fees.
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type(corp_type, filing_type)
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

    dist_code = DistributionCodeModel.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    # Update fee dist code to match the requirement.
    dist_code.client = "112"
    dist_code.responsibility_centre = "22222"
    dist_code.service_line = "33333"
    dist_code.stob = "4444"
    dist_code.project_code = "5555557"
    dist_code.service_fee_distribution_code_id = service_fee_dist_code.distribution_code_id
    dist_code.save()

    # GA
    jv_account_1 = factory_create_ejv_account(auth_account_id="1")

    # GI
    jv_account_3 = factory_create_ejv_account(auth_account_id="3", client="111")

    # Now create JV records.
    # Create EJV File model
    file_ref = f"INBOX.{datetime.now(tz=timezone.utc)}"
    ejv_file = EjvFileModel(
        file_ref=file_ref,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
        file_type=EjvFileType.PAYMENT.value,
    ).save()
    ejv_file_id = ejv_file.id

    feedback_content = (
        f"GABG...........00000000{ejv_file_id}...\n"
        f"..BH...0000................................................................................."
        f".....................................................................CGI\n"
    )

    jv_accounts = [jv_account_1, jv_account_3]
    inv_ids = []
    jv_account_ids = []
    inv_total_amount = 101.5
    for jv_acc in jv_accounts:
        jv_account_ids.append(jv_acc.id)
        inv = factory_invoice(
            payment_account=jv_acc,
            corp_type_code=corp_type,
            total=inv_total_amount,
            status_code=InvoiceStatus.REFUND_REQUESTED.value,
            payment_method_code=None,
        )
        factory_invoice_reference(inv.id, status_code=InvoiceReferenceStatus.ACTIVE.value)
        line = factory_payment_line_item(
            invoice_id=inv.id,
            fee_schedule_id=fee_schedule.fee_schedule_id,
            filing_fees=100,
            total=100,
            service_fees=1.5,
            fee_dist_id=dist_code.distribution_code_id,
        )
        inv_ids.append(inv.id)
        ejv_header = EjvHeaderModel(
            disbursement_status_code=DisbursementStatus.UPLOADED.value,
            ejv_file_id=ejv_file.id,
            payment_account_id=jv_acc.id,
        ).save()

        EjvLinkModel(
            link_id=inv.id,
            link_type=EJVLinkType.INVOICE.value,
            ejv_header_id=ejv_header.id,
            disbursement_status_code=DisbursementStatus.UPLOADED.value,
        ).save()
        inv_total = f"{inv.total:.2f}".zfill(15)
        pay_line_amount = f"{line.total:.2f}".zfill(15)
        service_fee_amount = f"{line.service_fees:.2f}".zfill(15)
        jh_and_jd = (
            f"..JH...FI0000000{ejv_header.id}.........................{inv_total}....................."
            f"............................................................................................"
            f"............................................................................................"
            f".........0000..............................................................................."
            f".......................................................................CGI\n"
            f"..JD...FI0000000{ejv_header.id}0000120230529................................................"
            f"...........{pay_line_amount}C................................................................."
            f"...................................{inv.id}                                             "
            f"                                                                0000........................"
            f"............................................................................................"
            f"..................................CGI\n"
            f"..JD...FI0000000{ejv_header.id}0000220230529................................................"
            f"...........{pay_line_amount}D................................................................."
            f"...................................{inv.id}                                             "
            f"                                                                0000........................"
            f"............................................................................................"
            f"..................................CGI\n"
            f"..JD...FI0000000{ejv_header.id}0000320230529..................................................."
            f"........{service_fee_amount}C................................................................."
            f"...................................{inv.id}                                             "
            f"                                                                0000........................"
            f"............................................................................................"
            f"..................................CGI\n"
            f"..JD...FI0000000{ejv_header.id}0000420230529................................................"
            f"...........{service_fee_amount}D.............................................................."
            f"......................................{inv.id}                                             "
            f"                                                                0000........................"
            f"............................................................................................"
            f"..................................CGI\n"
        )
        feedback_content = feedback_content + jh_and_jd
    feedback_content = (
        feedback_content + f"..BT.......FI0000000{ejv_header.id}000000000000002{inv_total}0000......."
        f"........................................................................."
        f"......................................................................CGI"
    )
    ack_file_name = f"ACK.{file_ref}"

    with open(ack_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write("")
        jv_file.close()

    upload_to_minio(str.encode(""), ack_file_name)

    add_file_event_to_queue_and_process(client, ack_file_name, QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)

    feedback_file_name = f"FEEDBACK.{file_ref}"

    with open(feedback_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    with open(feedback_file_name, "rb") as f:
        upload_to_minio(f.read(), feedback_file_name)

    mock_publish = Mock()
    mocker.patch("pay_api.services.gcp_queue.GcpQueue.publish", mock_publish)
    add_file_event_to_queue_and_process(client, feedback_file_name, QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value)
    # Query EJV File and assert the status is changed
    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.COMPLETED.value
    # Assert invoice and receipt records
    for inv_id in inv_ids:
        invoice = InvoiceModel.find_by_id(inv_id)
        assert invoice.disbursement_status_code is None
        assert invoice.invoice_status_code == InvoiceStatus.REFUNDED.value
        assert invoice.refund_date == datetime(2023, 5, 29)
        invoice_ref = InvoiceReferenceModel.find_by_invoice_id_and_status(
            inv_id, InvoiceReferenceStatus.COMPLETED.value
        )
        assert invoice_ref

    mock_publish.assert_called()
    # Assert payment records
    for jv_account_id in jv_account_ids:
        account = PaymentAccountModel.find_by_id(jv_account_id)
        payment = PaymentModel.search_account_payments(
            auth_account_id=account.auth_account_id,
            payment_status=PaymentStatus.COMPLETED.value,
            page=1,
            limit=100,
        )[0]
        assert len(payment) == 1
        assert payment[0][0].paid_amount == inv_total_amount


def test_successful_refund_reconciliations(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create a routing slip.
    # 2. Mark the routing slip for refund.
    # 3. Create a AP reconciliation file.
    # 4. Assert the status.
    rs_numbers = ("TEST00001", "TEST00002")
    for rs_number in rs_numbers:
        factory_routing_slip_account(
            number=rs_number,
            status=CfsAccountStatus.ACTIVE.value,
            total=100,
            remaining_amount=50,
            routing_slip_status=RoutingSlipStatus.REFUND_AUTHORIZED.value,
            refund_amount=50,
        )
        routing_slip = RoutingSlipModel.find_by_number(rs_number)
        factory_refund(
            routing_slip_id=routing_slip.id,
            details={
                "name": "TEST",
                "mailingAddress": {
                    "city": "Victoria",
                    "region": "BC",
                    "street": "655 Douglas St",
                    "country": "CA",
                    "postalCode": "V8V 0B6",
                    "streetAdditional": "",
                },
            },
        )
        routing_slip.status = RoutingSlipStatus.REFUND_UPLOADED.value

    # Now create AP records.
    # Create EJV File model
    file_ref = f"INBOX.{datetime.now()}"
    ejv_file = EjvFileModel(
        file_ref=file_ref,
        file_type=EjvFileType.REFUND.value,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()
    ejv_file_id = ejv_file.id

    # Upload an acknowledgement file
    ack_file_name = f"ACK.{file_ref}"

    with open(ack_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write("")
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    upload_to_minio(str.encode(""), ack_file_name)

    add_file_event_to_queue_and_process(client, ack_file_name, QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)

    # Now upload a feedback file and check the status.
    # Just create feedback file to mock the real feedback file.
    feedback_content = (
        f"APBG...........00000000{ejv_file_id}....\n"
        f"APBH...0000................................................................................."
        f".....................................................................CGI\n"
        f"APIH...000000000...{rs_numbers[0]}                                         ................"
        f"..........................................................................................."
        f"........................................................................................REF"
        f"UND_FAS...................................................................................."
        f"........................................................0000..............................."
        f"..........................................................................................."
        f"............................CGI\n"
        f"APNA...............{rs_numbers[0]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f".........................................0000.............................................."
        f"..........................................................................................."
        f".............CGI\n"
        f"APIL...............{rs_numbers[0]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f".....................................................................................0000.."
        f"..........................................................................................."
        f".........................................................CGI\n"
        f"APIC...............{rs_numbers[0]}                                         ................"
        f"............................0000..........................................................."
        f"........................................................................................"
        f"...CGI\n"
        f"APIH...000000000...{rs_numbers[1]}                                         ................"
        f"..........................................................................................."
        f"........................................................................................REF"
        f"UND_FAS...................................................................................."
        f"........................................................0000..............................."
        f"..........................................................................................."
        f"............................CGI\n"
        f"APNA...............{rs_numbers[1]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f".........................................0000.............................................."
        f"..........................................................................................."
        f".............CGI\n"
        f"APIL...............{rs_numbers[1]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f".....................................................................................0000.."
        f"..........................................................................................."
        f".........................................................CGI\n"
        f"APIC...............{rs_numbers[1]}                                         ................"
        f"............................0000..........................................................."
        f"........................................................................................"
        f"...CGI\n"
        f"APBT...........00000000{ejv_file_id}..............................0000....................."
        f"..........................................................................................."
        f"......................................CGI\n"
    )
    feedback_file_name = f"FEEDBACK.{file_ref}"

    with open(feedback_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    with open(feedback_file_name, "rb") as f:
        upload_to_minio(f.read(), feedback_file_name)

    add_file_event_to_queue_and_process(client, feedback_file_name, QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value)

    # Query EJV File and assert the status is changed
    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.COMPLETED.value
    for rs_number in rs_numbers:
        routing_slip = RoutingSlipModel.find_by_number(rs_number)
        assert routing_slip.status == RoutingSlipStatus.REFUND_PROCESSED.value
        assert routing_slip.refund_status == ChequeRefundStatus.PROCESSED.value


def test_failed_refund_reconciliations(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create a routing slip.
    # 2. Mark the routing slip for refund.
    # 3. Create a AP reconciliation file.
    # 4. Assert the status.
    rs_numbers = ("TEST00001", "TEST00002")
    for rs_number in rs_numbers:
        factory_routing_slip_account(
            number=rs_number,
            status=CfsAccountStatus.ACTIVE.value,
            total=100,
            remaining_amount=50,
            routing_slip_status=RoutingSlipStatus.REFUND_AUTHORIZED.value,
            refund_amount=50,
        )
        routing_slip = RoutingSlipModel.find_by_number(rs_number)
        factory_refund(
            routing_slip_id=routing_slip.id,
            details={
                "name": "TEST",
                "mailingAddress": {
                    "city": "Victoria",
                    "region": "BC",
                    "street": "655 Douglas St",
                    "country": "CA",
                    "postalCode": "V8V 0B6",
                    "streetAdditional": "",
                },
            },
        )
        routing_slip.status = RoutingSlipStatus.REFUND_UPLOADED.value

    # Now create AP records.
    # Create EJV File model
    file_ref = f"INBOX.{datetime.now()}"
    ejv_file = EjvFileModel(
        file_ref=file_ref,
        file_type=EjvFileType.REFUND.value,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()
    ejv_file_id = ejv_file.id

    # Upload an acknowledgement file
    ack_file_name = f"ACK.{file_ref}"

    with open(ack_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write("")
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    upload_to_minio(str.encode(""), ack_file_name)

    add_file_event_to_queue_and_process(client, ack_file_name, QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)

    # Now upload a feedback file and check the status.
    # Just create feedback file to mock the real feedback file.
    # Set first routing slip to be success and second to ve failed
    feedback_content = (
        f"APBG...........00000000{ejv_file_id}....\n"
        f"APBH...0000................................................................................."
        f".....................................................................CGI\n"
        f"APIH...000000000...{rs_numbers[0]}                                         ................"
        f"..........................................................................................."
        f"........................................................................................REF"
        f"UND_FAS...................................................................................."
        f"........................................................0000..............................."
        f"..........................................................................................."
        f"............................CGI\n"
        f"APNA...............{rs_numbers[0]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f".........................................0000.............................................."
        f"..........................................................................................."
        f".............CGI\n"
        f"APIL...............{rs_numbers[0]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f".....................................................................................0000.."
        f"..........................................................................................."
        f".........................................................CGI\n"
        f"APIC...............{rs_numbers[0]}                                         ................"
        f"............................0000..........................................................."
        f"........................................................................................"
        f"...CGI\n"
        f"APIH...000000000...{rs_numbers[1]}                                         ................"
        f"..........................................................................................."
        f"........................................................................................REF"
        f"UND_FAS...................................................................................."
        f"........................................................0001..............................."
        f"..........................................................................................."
        f"............................CGI\n"
        f"APNA...............{rs_numbers[1]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f".........................................0001.............................................."
        f"..........................................................................................."
        f".............CGI\n"
        f"APIL...............{rs_numbers[1]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f".....................................................................................0001.."
        f"..........................................................................................."
        f".........................................................CGI\n"
        f"APIC...............{rs_numbers[1]}                                         ................"
        f"............................0001..........................................................."
        f"........................................................................................"
        f"...CGI\n"
        f"APBT...........00000000{ejv_file_id}..............................0000....................."
        f"..........................................................................................."
        f"......................................CGI\n"
    )
    feedback_file_name = f"FEEDBACK.{file_ref}"

    with open(feedback_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    with open(feedback_file_name, "rb") as f:
        upload_to_minio(f.read(), feedback_file_name)

    add_file_event_to_queue_and_process(client, feedback_file_name, QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value)

    # Query EJV File and assert the status is changed
    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.COMPLETED.value
    routing_slip_1 = RoutingSlipModel.find_by_number(rs_numbers[0])
    assert routing_slip_1.status == RoutingSlipStatus.REFUND_PROCESSED.value
    assert routing_slip_1.refund_status == ChequeRefundStatus.PROCESSED.value

    routing_slip_2 = RoutingSlipModel.find_by_number(rs_numbers[1])
    assert routing_slip_2.status == RoutingSlipStatus.REFUND_REJECTED.value


def test_successful_eft_refund_reconciliations(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create EFT refund.
    # 2. Create a AP reconciliation file.
    # 3. Assert the status.
    eft_short_name_names = ("TEST00001", "TEST00002")
    eft_refund_ids = []
    for eft_short_name_name in eft_short_name_names:
        factory_create_eft_shortname(short_name=eft_short_name_name)
        eft_short_name = EftShortNameModel.find_by_short_name(eft_short_name_name, EFTShortnameType.EFT.value)
        eft_refund = factory_create_eft_refund(
            disbursement_status_code=DisbursementStatus.ACKNOWLEDGED.value,
            refund_amount=100,
            refund_email="test@test.com",
            short_name_id=eft_short_name.id,
            status=EFTShortnameRefundStatus.APPROVED.value,
            comment=eft_short_name.short_name,
        )
        eft_refund_ids.append(str(eft_refund.id).zfill(9))

    # Now create AP records.
    # Create EJV File model
    file_ref = f"INBOX.{datetime.now()}"
    ejv_file = EjvFileModel(
        file_ref=file_ref,
        file_type=EjvFileType.EFT_REFUND.value,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()

    ejv_file_id = ejv_file.id

    # Upload an acknowledgement file
    ack_file_name = f"ACK.{file_ref}"

    with open(ack_file_name, "a+") as jv_file:
        jv_file.write("")
        jv_file.close()

    # Upload the ACK file to minio and publish message.
    upload_to_minio(str.encode(""), ack_file_name)

    add_file_event_to_queue_and_process(client, ack_file_name, QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)

    # Create and upload a feedback file and check the status.
    feedback_content = (
        f"APBG...........00000000{ejv_file_id}....\n"
        f"APBH...0000................................................................................"
        f"......................................................................CGI\n"
        f"APIH...000000000...{eft_refund_ids[0]}                                         ............"
        f"..........................................................................................."
        f"..........................................................................................."
        f".REFUND_EFT................................................................................"
        f"............................................................0000..........................."
        f"..........................................................................................."
        f"................................CGI\n"
        f"APIL...............{eft_refund_ids[0]}                                         ............"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"........................................................................................."
        f"0000......................................................................................."
        f"...............................................................CGI\n"
        f"APIC...............{eft_short_name_names[0]}                                         ......"
        f"......................................0000................................................."
        f"..........................................................................................."
        f"..........CGI\n"
        f"APIH...000000000...{eft_refund_ids[1]}                                         ............"
        f"..........................................................................................."
        f"..........................................................................................."
        f".REFUND_EFT................................................................................"
        f"............................................................0000..........................."
        f"..........................................................................................."
        f"................................CGI\n"
        f"APIL...............{eft_refund_ids[1]}                                         ............"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"........................................................................................."
        f"0000......................................................................................."
        f"...............................................................CGI\n"
        f"APIC...............{eft_short_name_names[1]}                                         ......"
        f"......................................0000................................................."
        f"..........................................................................................."
        f"..........CGI\n"
        f"APBT...........00000000{ejv_file_id}..............................0000....................."
        f"..........................................................................................."
        f"......................................CGI\n"
    )
    feedback_file_name = f"FEEDBACK.{file_ref}"

    with open(feedback_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    with open(feedback_file_name, "rb") as f:
        upload_to_minio(f.read(), feedback_file_name)

    add_file_event_to_queue_and_process(client, feedback_file_name, QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value)

    # Query EJV File and assert the status is changed
    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.COMPLETED.value
    for eft_refund_id in eft_refund_ids:
        eft_refund = EFTRefundModel.find_by_id(eft_refund_id)
        assert eft_refund.status == EFTShortnameRefundStatus.COMPLETED.value
        assert eft_refund.disbursement_status_code == DisbursementStatus.COMPLETED.value
        assert eft_refund.disbursement_date


def test_failed_eft_refund_reconciliations(session, app, client):
    """Test Reconciliations worker."""
    # 1. Create EFT refund.
    # 2. Create a AP reconciliation file.
    # 3. Assert the status.
    eft_short_name_names = ("TEST00001", "TEST00002")
    eft_refund_ids = []
    for eft_short_name_name in eft_short_name_names:
        factory_create_eft_shortname(short_name=eft_short_name_name)
        eft_short_name = EftShortNameModel.find_by_short_name(eft_short_name_name, EFTShortnameType.EFT.value)
        eft_refund = factory_create_eft_refund(
            disbursement_status_code=DisbursementStatus.ACKNOWLEDGED.value,
            refund_amount=100,
            refund_email="test@test.com",
            short_name_id=eft_short_name.id,
            status=EFTShortnameRefundStatus.APPROVED.value,
            comment=eft_short_name.short_name,
        )
        eft_refund_ids.append(str(eft_refund.id).zfill(9))

    # Now create AP records.
    # Create EJV File model
    file_ref = f"INBOX.{datetime.now()}"
    ejv_file = EjvFileModel(
        file_ref=file_ref,
        file_type=EjvFileType.EFT_REFUND.value,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()

    ejv_file_id = ejv_file.id

    # Upload an acknowledgement file
    ack_file_name = f"ACK.{file_ref}"

    with open(ack_file_name, "a+") as jv_file:
        jv_file.write("")
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    upload_to_minio(str.encode(""), ack_file_name)

    add_file_event_to_queue_and_process(client, ack_file_name, QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)

    # Create and upload a feedback file and check the status.
    feedback_content = (
        f"APBG...........00000000{ejv_file_id}....\n"
        f"APBH...0000................................................................................"
        f"......................................................................CGI\n"
        f"APIH...000000000...{eft_refund_ids[0]}                                         ............"
        f"..........................................................................................."
        f"..........................................................................................."
        f".REFUND_EFT................................................................................"
        f"............................................................0000..........................."
        f"..........................................................................................."
        f"................................CGI\n"
        f"APIL...............{eft_refund_ids[0]}                                         ............"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"........................................................................................."
        f"0000......................................................................................."
        f"...............................................................CGI\n"
        f"APIC...............{eft_short_name_names[0]}                                         ......"
        f"......................................0000................................................."
        f"..........................................................................................."
        f"..........CGI\n"
        f"APIH...000000000...{eft_refund_ids[1]}                                         ............"
        f"..........................................................................................."
        f"..........................................................................................."
        f".REFUND_EFT................................................................................"
        f"............................................................0001..........................."
        f"..........................................................................................."
        f"................................CGI\n"
        f"APIL...............{eft_refund_ids[1]}                                         ............"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"........................................................................................."
        f"0001......................................................................................."
        f"...............................................................CGI\n"
        f"APIC...............{eft_short_name_names[1]}                                         ......"
        f"......................................0001................................................."
        f"..........................................................................................."
        f"..........CGI\n"
        f"APBT...........00000000{ejv_file_id}..............................0000....................."
        f"..........................................................................................."
        f"......................................CGI\n"
    )
    feedback_file_name = f"FEEDBACK.{file_ref}"

    with open(feedback_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    with open(feedback_file_name, "rb") as f:
        upload_to_minio(f.read(), feedback_file_name)

    add_file_event_to_queue_and_process(client, feedback_file_name, QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value)

    # Query EJV File and assert the status is changed
    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.COMPLETED.value
    eft_refund = EFTRefundModel.find_by_id(eft_refund_ids[0])
    assert eft_refund.status == EFTShortnameRefundStatus.COMPLETED.value
    assert eft_refund.disbursement_status_code == DisbursementStatus.COMPLETED.value
    assert eft_refund.disbursement_date

    eft_refund2 = EFTRefundModel.find_by_id(eft_refund_ids[1])
    assert eft_refund2.status == EFTShortnameRefundStatus.ERRORED.value
    assert eft_refund2.disbursement_status_code == DisbursementStatus.ERRORED.value


@pytest.mark.skip(reason="Unused, BCA not currently in production")
def test_successful_ap_disbursement(session, app, client):
    """Test Reconciliations worker for ap disbursement."""
    # 1. Create invoice.
    # 2. Create a AP reconciliation file.
    # 3. Assert the status.
    invoice_ids = []
    account = factory_create_pad_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    invoice = factory_invoice(
        payment_account=account,
        status_code=InvoiceStatus.PAID.value,
        total=10,
        corp_type_code="BCA",
    )

    invoice_ids.append(invoice.id)
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("BCA", "OLAARTOQ")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    refund_invoice = factory_invoice(
        payment_account=account,
        status_code=InvoiceStatus.REFUNDED.value,
        total=10,
        disbursement_status_code=DisbursementStatus.COMPLETED.value,
        corp_type_code="BCA",
    )
    invoice_ids.append(refund_invoice.id)

    line = factory_payment_line_item(refund_invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    factory_refund(invoice_id=refund_invoice.id)

    file_ref = f"INBOX.{datetime.now()}"
    ejv_file = EjvFileModel(
        file_ref=file_ref,
        file_type=EjvFileType.NON_GOV_DISBURSEMENT.value,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()
    ejv_file_id = ejv_file.id

    ejv_header = EjvHeaderModel(
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
        ejv_file_id=ejv_file.id,
        payment_account_id=account.id,
    ).save()

    EjvLinkModel(
        link_id=invoice.id,
        link_type=EJVLinkType.INVOICE.value,
        ejv_header_id=ejv_header.id,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()

    EjvLinkModel(
        link_id=refund_invoice.id,
        link_type=EJVLinkType.INVOICE.value,
        ejv_header_id=ejv_header.id,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()

    ack_file_name = f"ACK.{file_ref}"

    with open(ack_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write("")
        jv_file.close()

    upload_to_minio(str.encode(""), ack_file_name)

    add_file_event_to_queue_and_process(client, ack_file_name, QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)

    invoice_str = [str(invoice_id).zfill(9) for invoice_id in invoice_ids]
    feedback_content = (
        f"APBG...........{str(ejv_file_id).zfill(9)}....\n"
        f"APBH...0000................................................................................."
        f".....................................................................CGI\n"
        f"APIH...000000000...{invoice_str[0]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"........................................................0000..............................."
        f"..........................................................................................."
        f"............................CGI\n"
        f"APNA...............{invoice_str[0]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f".........................................0000.............................................."
        f"..........................................................................................."
        f".............CGI\n"
        f"APIL...............{invoice_str[0]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f".....................................................................................0000.."
        f"..........................................................................................."
        f".........................................................CGI\n"
        f"APIC...............{invoice_str[0]}                                         ................"
        f"............................0000..........................................................."
        f"........................................................................................"
        f"...CGI\n"
        f"APIH...000000000...{invoice_str[1]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"........................................................0000..............................."
        f"..........................................................................................."
        f"............................CGI\n"
        f"APNA...............{invoice_str[1]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f".........................................0000.............................................."
        f"..........................................................................................."
        f".............CGI\n"
        f"APIL...............{invoice_str[1]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f".....................................................................................0000.."
        f"..........................................................................................."
        f".........................................................CGI\n"
        f"APIC...............{invoice_str[1]}                                         ................"
        f"............................0000..........................................................."
        f"........................................................................................"
        f"...CGI\n"
        f"APBT...........00000000{ejv_file_id}..............................0000....................."
        f"..........................................................................................."
        f"......................................CGI\n"
    )

    feedback_file_name = f"FEEDBACK.{file_ref}"

    with open(feedback_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()

    with open(feedback_file_name, "rb") as f:
        upload_to_minio(f.read(), feedback_file_name)

    add_file_event_to_queue_and_process(client, feedback_file_name, QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.COMPLETED.value
    for invoice_id in invoice_ids:
        invoice = InvoiceModel.find_by_id(invoice_id)
        if invoice.invoice_status_code == InvoiceStatus.PAID.value:
            assert invoice.disbursement_status_code == DisbursementStatus.COMPLETED.value
            assert invoice.disbursement_date is not None
        if invoice.invoice_status_code == InvoiceStatus.REFUNDED.value:
            assert invoice.disbursement_status_code == DisbursementStatus.REVERSED.value
            assert invoice.disbursement_reversal_date is not None
            refund = RefundModel.find_by_invoice_id(invoice.id)
            assert refund.gl_posted is not None


@pytest.mark.skip(reason="Unused, BCA not currently in production")
def test_failure_ap_disbursement(session, app, client):
    """Test Reconciliations worker for ap disbursement."""
    # 1. Create invoice.
    # 2. Create a AP reconciliation file.
    # 3. Assert the status.
    invoice_ids = []
    account = factory_create_pad_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    invoice = factory_invoice(
        payment_account=account,
        status_code=InvoiceStatus.PAID.value,
        total=10,
        corp_type_code="BCA",
    )
    invoice_ids.append(invoice.id)
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("BCA", "OLAARTOQ")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    refund_invoice = factory_invoice(
        payment_account=account,
        status_code=InvoiceStatus.REFUNDED.value,
        total=10,
        disbursement_status_code=DisbursementStatus.COMPLETED.value,
        corp_type_code="BCA",
    )
    invoice_ids.append(refund_invoice.id)
    line = factory_payment_line_item(refund_invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    factory_refund(invoice_id=refund_invoice.id)

    file_ref = f"INBOX.{datetime.now()}"
    ejv_file = EjvFileModel(
        file_ref=file_ref,
        file_type=EjvFileType.NON_GOV_DISBURSEMENT.value,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()
    ejv_file_id = ejv_file.id

    ejv_header = EjvHeaderModel(
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
        ejv_file_id=ejv_file.id,
        payment_account_id=account.id,
    ).save()

    EjvLinkModel(
        link_id=invoice.id,
        link_type=EJVLinkType.INVOICE.value,
        ejv_header_id=ejv_header.id,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()

    EjvLinkModel(
        link_id=refund_invoice.id,
        link_type=EJVLinkType.INVOICE.value,
        ejv_header_id=ejv_header.id,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
    ).save()

    ack_file_name = f"ACK.{file_ref}"

    with open(ack_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write("")
        jv_file.close()

    upload_to_minio(str.encode(""), ack_file_name)

    add_file_event_to_queue_and_process(client, ack_file_name, QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)

    # We need this, otherwise the feedback_content file will need to be changed.
    invoice_str = [str(invoice_id).zfill(9) for invoice_id in invoice_ids]
    # Now upload a feedback file and check the status.
    # Just create feedback file to mock the real feedback file.
    # Set first invoice to be success and second to be failed
    feedback_content = (
        f"APBG...........{str(ejv_file_id).zfill(9)}....\n"
        f"APBH...0000................................................................................."
        f".....................................................................CGI\n"
        f"APIH...000000000...{invoice_str[0]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"........................................................0000..............................."
        f"..........................................................................................."
        f"............................CGI\n"
        f"APNA...............{invoice_str[0]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f".........................................0000.............................................."
        f"..........................................................................................."
        f".............CGI\n"
        f"APIL...............{invoice_str[0]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f".....................................................................................0000.."
        f"..........................................................................................."
        f".........................................................CGI\n"
        f"APIC...............{invoice_str[0]}                                         ................"
        f"............................0000..........................................................."
        f"........................................................................................"
        f"...CGI\n"
        f"APIH...000000000...{invoice_str[1]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"........................................................0001..............................."
        f"..........................................................................................."
        f"............................CGI\n"
        f"APNA...............{invoice_str[1]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f".........................................0001.............................................."
        f"..........................................................................................."
        f".............CGI\n"
        f"APIL...............{invoice_str[1]}                                         ................"
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f"..........................................................................................."
        f".....................................................................................0001.."
        f"..........................................................................................."
        f".........................................................CGI\n"
        f"APIC...............{invoice_str[1]}                                         ................"
        f"............................0001..........................................................."
        f"........................................................................................"
        f"...CGI\n"
        f"APBT...........00000000{ejv_file_id}..............................0000....................."
        f"..........................................................................................."
        f"......................................CGI\n"
    )
    feedback_file_name = f"FEEDBACK.{file_ref}"

    with open(feedback_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()

    with open(feedback_file_name, "rb") as f:
        upload_to_minio(f.read(), feedback_file_name)

    add_file_event_to_queue_and_process(client, feedback_file_name, QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.COMPLETED.value
    invoice_1 = InvoiceModel.find_by_id(invoice_ids[0])
    assert invoice_1.disbursement_status_code == DisbursementStatus.COMPLETED.value
    assert invoice_1.disbursement_date is not None
    invoice_link = db.session.query(EjvLinkModel).filter(EjvLinkModel.link_id == invoice_ids[0]).one_or_none()
    assert invoice_link.disbursement_status_code == DisbursementStatus.COMPLETED.value

    invoice_2 = InvoiceModel.find_by_id(invoice_ids[1])
    assert invoice_2.disbursement_status_code == DisbursementStatus.ERRORED.value
    invoice_link = db.session.query(EjvLinkModel).filter(EjvLinkModel.link_id == invoice_ids[1]).one_or_none()
    assert invoice_link.disbursement_status_code == DisbursementStatus.ERRORED.value


def test_successful_partial_refund_ejv_reconciliations(session, app, client, mocker):
    """Test successful partial refund EJV reconciliations with link_type=PARTIAL_REFUND."""
    # 1. Create EJV payment accounts
    # 2. Create invoice and related records
    # 3. Create partial refund records
    # 4. Create a feedback file and assert status
    corp_type = "CP"
    filing_type = "OTFDR"

    InvoiceModel.query.delete()
    # Reset the sequence, because the unit test is only dealing with 1 character for the invoice id.
    # This becomes more apparent when running unit tests in parallel.
    db.session.execute(text("ALTER SEQUENCE invoices_id_seq RESTART WITH 1"))
    db.session.commit()

    # Find fee schedule which have service fees.
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type(corp_type, filing_type)
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

    dist_code = DistributionCodeModel.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    # Update fee dist code to match the requirement.
    dist_code.client = "112"
    dist_code.responsibility_centre = "22222"
    dist_code.service_line = "33333"
    dist_code.stob = "4444"
    dist_code.project_code = "5555555"
    dist_code.service_fee_distribution_code_id = service_fee_dist_code.distribution_code_id
    dist_code.save()

    # GA
    jv_account_1 = factory_create_ejv_account(auth_account_id="1")
    
    #GI
    jv_account_2 = factory_create_ejv_account(auth_account_id="2", client="111")

    # Create EJV File
    file_ref = f"INBOX.{datetime.now(tz=timezone.utc)}"
    ejv_file = EjvFileModel(
        file_ref=file_ref,
        disbursement_status_code=DisbursementStatus.UPLOADED.value,
        file_type=EjvFileType.PAYMENT.value,
    ).save()
    ejv_file_id = ejv_file.id

    feedback_content = (
        f"GABG...........00000000{ejv_file_id}...\n"
        f"..BH...0000................................................................................."
        f".....................................................................CGI\n"
    )

    jv_accounts = [jv_account_1, jv_account_2]
    inv_ids = []
    partial_refund_ids = []
    jv_account_ids = []
    inv_total_amount = 100.0
    refund_amount = 40.0

    for jv_acc in jv_accounts:
        jv_account_ids.append(jv_acc.id)
        inv = factory_invoice(
            payment_account=jv_acc,
            corp_type_code=corp_type,
            total=inv_total_amount,
            status_code=InvoiceStatus.PAID.value,
            payment_method_code=PaymentMethod.EJV.value,
        )
        factory_invoice_reference(inv.id, status_code=InvoiceReferenceStatus.COMPLETED.value)

        line = factory_payment_line_item(
            invoice_id=inv.id,
            fee_schedule_id=fee_schedule.fee_schedule_id,
            filing_fees=100,
            total=inv_total_amount,
            service_fees=0.0,
            fee_dist_id=dist_code.distribution_code_id,
        )
        inv_ids.append(inv.id)
        
        partial_refund = RefundsPartialModel(
            invoice_id=inv.id,
            status=RefundsPartialStatus.REFUND_PROCESSING.value,
            payment_line_item_id=line.id,
            refund_amount=refund_amount,
            created_by='test',
            created_name='test',
            version=1
        )
        partial_refund.save()
        partial_refund_ids.append(partial_refund.id)

        ejv_header = EjvHeaderModel(
            disbursement_status_code=DisbursementStatus.UPLOADED.value,
            ejv_file_id=ejv_file.id,
            payment_account_id=jv_acc.id,
        ).save()

        EjvLinkModel(
            link_id=partial_refund.id,
            link_type=EJVLinkType.PARTIAL_REFUND.value,
            ejv_header_id=ejv_header.id,
            disbursement_status_code=DisbursementStatus.UPLOADED.value,
        ).save()
        
        flowthrough = f"{inv.id}-PR-{partial_refund.id}"
        refund_amount_str = f"{refund_amount:.2f}".zfill(15)

        jh_and_jd = (
            f"..JH...FI0000000{ejv_header.id}.........................{refund_amount_str}....................."
            f"............................................................................................"
            f"............................................................................................"
            f".........0000..............................................................................."
            f".......................................................................CGI\n"
            f"..JD...FI0000000{ejv_header.id}0000120230529................................................"
            f"...........{refund_amount_str}C..............................................................."
            f".....................................{flowthrough}                                      "
            f"                                                                0000........................"
            f"............................................................................................"
            f"..................................CGI\n"
            f"..JD...FI0000000{ejv_header.id}0000220230529................................................"
            f"...........{refund_amount_str}D..............................................................."
            f".....................................{flowthrough}                                      "
            f"                                                                0000........................"
            f"............................................................................................"
            f"..................................CGI\n"
        )
        feedback_content = feedback_content + jh_and_jd
        
    feedback_content = (
        feedback_content + f"..BT.......FI0000000{ejv_header.id}000000000000002{refund_amount_str}0000......."
        f"........................................................................."
        f"......................................................................CGI"
    )

    ack_file_name = f"ACK.{file_ref}"
    with open(ack_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write("")
        jv_file.close()

    upload_to_minio(str.encode(""), ack_file_name)

    add_file_event_to_queue_and_process(client, ack_file_name, QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value)

    feedback_file_name = f"FEEDBACK.{file_ref}"
    with open(feedback_file_name, "a+", encoding="utf-8") as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()
    with open(feedback_file_name, "rb") as f:
        upload_to_minio(f.read(), feedback_file_name)

    mock_publish = Mock()
    mocker.patch("pay_api.services.gcp_queue.GcpQueue.publish", mock_publish)

    mocker.patch('pay_api.models.RefundsPartial.find_by_id', 
                 side_effect=lambda id: next((r for r in RefundsPartialModel.query.all() if r.id == id), None))

    add_file_event_to_queue_and_process(client, feedback_file_name, QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value)

    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.COMPLETED.value

    for i, inv_id in enumerate(inv_ids):
        invoice = InvoiceModel.find_by_id(inv_id)
        partial_refund = RefundsPartialModel.find_by_id(partial_refund_ids[i])

        assert invoice.invoice_status_code == InvoiceStatus.PAID.value
        assert partial_refund.status == RefundsPartialStatus.REFUND_PROCESSED.value
        assert partial_refund.gl_posted is not None
