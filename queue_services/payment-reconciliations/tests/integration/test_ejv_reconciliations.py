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

"""Tests to assure the Payment Reconciliation.

Test-Suite to ensure that the Payment Reconciliation queue service is working as expected.
"""

from datetime import datetime

import pytest
from entity_queue_common.service_utils import subscribe_to_queue
from flask import current_app
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import EjvInvoiceLink as EjvInvoiceLinkModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.utils.enums import (
    CfsAccountStatus, DisbursementStatus, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod)

from .factory import (
    factory_create_pad_account, factory_distribution, factory_invoice, factory_invoice_reference,
    factory_payment_line_item)
from .utils import helper_add_ejv_event_to_queue, upload_to_minio


@pytest.mark.asyncio
async def test_succesful_ejv_reconciliations(session, app, stan_server, event_loop, client_id, events_stan, future,
                                             mock_publish):
    """Test Reconciliations worker."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    # Create a Credit Card Payment
    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = '1234'
    partner_code = 'VS'
    fee_schedule: FeeScheduleModel = FeeScheduleModel.find_by_filing_type_and_corp_type(
        corp_type_code=partner_code, filing_type_code='WILLSEARCH'
    )

    pay_account: PaymentAccountModel = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value,
                                                                  account_number=cfs_account_number)
    invoice: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                            corp_type_code='VS',
                                            payment_method_code=PaymentMethod.ONLINE_BANKING.value,
                                            status_code=InvoiceStatus.PAID.value)
    line_item: PaymentLineItemModel = factory_payment_line_item(
        invoice_id=invoice.id, filing_fees=90.0, service_fees=10.0, total=90.0,
        fee_schedule_id=fee_schedule.fee_schedule_id
    )
    dist_code: DistributionCodeModel = DistributionCodeModel.find_by_id(line_item.fee_distribution_id)
    # Check if the disbursement distribution is present for this.
    if not dist_code.disbursement_distribution_code_id:
        disbursement_distribution_code: DistributionCodeModel = factory_distribution(name='Disbursement')
        dist_code.disbursement_distribution_code_id = disbursement_distribution_code.distribution_code_id
        dist_code.save()

    invoice_number = '1234567890'
    factory_invoice_reference(
        invoice_id=invoice.id, invoice_number=invoice_number, status_code=InvoiceReferenceStatus.COMPLETED.value
    )
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()

    # Now create JV records.
    # Create EJV File model
    file_ref = f'INBOX.{datetime.now()}'
    ejv_file: EjvFileModel = EjvFileModel(file_ref=file_ref,
                                          disbursement_status_code=DisbursementStatus.UPLOADED.value).save()
    ejv_file_id = ejv_file.id

    ejv_header: EjvHeaderModel = EjvHeaderModel(disbursement_status_code=DisbursementStatus.UPLOADED.value,
                                                ejv_file_id=ejv_file.id,
                                                partner_code=partner_code,
                                                payment_account_id=pay_account.id).save()
    EjvInvoiceLinkModel(
        invoice_id=invoice.id, ejv_header_id=ejv_header.id, disbursement_status_code=DisbursementStatus.UPLOADED.value
    ).save()

    ack_file_name = f'ACK.{file_ref}'

    with open(ack_file_name, 'a+') as jv_file:
        jv_file.write('')
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    upload_to_minio(file_name=ack_file_name, value_as_bytes=str.encode(''))

    await helper_add_ejv_event_to_queue(events_stan, file_name=ack_file_name)

    # Query EJV File and assert the status is changed
    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.ACKNOWLEDGED.value

    # Now upload a feedback file and check the status.
    # Just create feedback file to mock the real feedback file.
    feedback_content = f'..BG...........00000000{ejv_file.id}...\n' \
                       f'..BH...0000.................................................................................' \
                       f'.....................................................................CGI\n' \
                       f'..JH...FI0000000{ejv_header.id}.........................000000000090.00.....................' \
                       f'............................................................................................' \
                       f'............................................................................................' \
                       f'.........0000...............................................................................' \
                       f'.......................................................................CGI\n' \
                       f'..JD...FI0000000{ejv_header.id}00001........................................................' \
                       f'...........000000000090.00D.................................................................' \
                       f'...................................{invoice.id}                                             ' \
                       f'                                                                0000........................' \
                       f'............................................................................................' \
                       f'..................................CGI\n' \
                       f'..JD...FI0000000{ejv_header.id}00002........................................................' \
                       f'...........000000000090.00C.................................................................' \
                       f'...................................{invoice.id}                                             ' \
                       f'                                                                0000........................' \
                       f'............................................................................................' \
                       f'..................................CGI\n' \
                       f'..BT.......FI0000000{ejv_header.id}000000000000002000000000090.000000.......................' \
                       f'............................................................................................' \
                       f'...................................CGI'

    feedback_file_name = f'FEEDBACK.{file_ref}'

    with open(feedback_file_name, 'a+') as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    with open(feedback_file_name, 'rb') as f:
        upload_to_minio(f.read(), feedback_file_name)
    # upload_to_minio(file_name=feedback_file_name, value_as_bytes=feedback_content.encode())

    await helper_add_ejv_event_to_queue(events_stan, file_name=feedback_file_name, message_type='FEEDBACKReceived')

    # Query EJV File and assert the status is changed
    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.COMPLETED.value
    invoice = InvoiceModel.find_by_id(invoice.id)
    assert invoice.disbursement_status_code == DisbursementStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_failed_ejv_reconciliations(session, app, stan_server, event_loop, client_id, events_stan, future,
                                          mock_publish):
    """Test Reconciliations worker."""
    # Call back for the subscription
    from reconciliations.worker import cb_subscription_handler

    # Create a Credit Card Payment
    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('subject'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('queue'),
                             current_app.config.get('SUBSCRIPTION_OPTIONS').get('durable_name'),
                             cb_subscription_handler)

    # 1. Create payment account
    # 2. Create invoice and related records
    # 3. Create CFS Invoice records
    # 4. Create a CFS settlement file, and verify the records
    cfs_account_number = '1234'
    partner_code = 'VS'
    fee_schedule: FeeScheduleModel = FeeScheduleModel.find_by_filing_type_and_corp_type(
        corp_type_code=partner_code, filing_type_code='WILLSEARCH'
    )

    pay_account: PaymentAccountModel = factory_create_pad_account(status=CfsAccountStatus.ACTIVE.value,
                                                                  account_number=cfs_account_number)
    invoice: InvoiceModel = factory_invoice(payment_account=pay_account, total=100, service_fees=10.0,
                                            corp_type_code='VS',
                                            payment_method_code=PaymentMethod.ONLINE_BANKING.value,
                                            status_code=InvoiceStatus.PAID.value)
    line_item: PaymentLineItemModel = factory_payment_line_item(
        invoice_id=invoice.id, filing_fees=90.0, service_fees=10.0, total=90.0,
        fee_schedule_id=fee_schedule.fee_schedule_id
    )
    dist_code: DistributionCodeModel = DistributionCodeModel.find_by_id(line_item.fee_distribution_id)
    # Check if the disbursement distribution is present for this.
    if not dist_code.disbursement_distribution_code_id:
        disbursement_distribution_code: DistributionCodeModel = factory_distribution(name='Disbursement')
        dist_code.disbursement_distribution_code_id = disbursement_distribution_code.distribution_code_id
        dist_code.save()
    disbursement_distribution_code_id = dist_code.disbursement_distribution_code_id

    invoice_number = '1234567890'
    factory_invoice_reference(
        invoice_id=invoice.id, invoice_number=invoice_number, status_code=InvoiceReferenceStatus.COMPLETED.value
    )
    invoice.invoice_status_code = InvoiceStatus.SETTLEMENT_SCHEDULED.value
    invoice = invoice.save()

    # Now create JV records.
    # Create EJV File model
    file_ref = f'INBOX{datetime.now()}'
    ejv_file: EjvFileModel = EjvFileModel(file_ref=file_ref,
                                          disbursement_status_code=DisbursementStatus.UPLOADED.value).save()
    ejv_file_id = ejv_file.id

    ejv_header: EjvHeaderModel = EjvHeaderModel(disbursement_status_code=DisbursementStatus.UPLOADED.value,
                                                ejv_file_id=ejv_file.id,
                                                partner_code=partner_code,
                                                payment_account_id=pay_account.id).save()
    EjvInvoiceLinkModel(
        invoice_id=invoice.id, ejv_header_id=ejv_header.id, disbursement_status_code=DisbursementStatus.UPLOADED.value
    ).save()

    ack_file_name = f'ACK.{file_ref}'

    with open(ack_file_name, 'a+') as jv_file:
        jv_file.write('')
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    upload_to_minio(file_name=ack_file_name, value_as_bytes=str.encode(''))

    await helper_add_ejv_event_to_queue(events_stan, file_name=ack_file_name)

    # Query EJV File and assert the status is changed
    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.ACKNOWLEDGED.value

    # Now upload a feedback file and check the status.
    # Just create feedback file to mock the real feedback file.
    feedback_content = f'..BG...........00000000{ejv_file.id}...\n' \
                       f'..BH...1111TESTERRORMESSAGE................................................................' \
                       f'......................................................................CGI\n' \
                       f'..JH...FI0000000{ejv_header.id}.........................000000000090.00....................' \
                       f'...........................................................................................' \
                       f'...........................................................................................' \
                       f'............1111TESTERRORMESSAGE...........................................................' \
                       f'...........................................................................CGI\n' \
                       f'..JD...FI0000000{ejv_header.id}00001.......................................................' \
                       f'............000000000090.00D...............................................................' \
                       f'.....................................{invoice.id}                                          ' \
                       f'                                                                   1111TESTERRORMESSAGE....' \
                       f'...........................................................................................' \
                       f'.......................................CGI\n' \
                       f'..JD...FI0000000{ejv_header.id}00002.......................................................' \
                       f'............000000000090.00C...............................................................' \
                       f'.....................................{invoice.id}                                          ' \
                       f'                                                                   1111TESTERRORMESSAGE....' \
                       f'...........................................................................................' \
                       f'.......................................CGI\n' \
                       f'..BT...........FI0000000{ejv_header.id}000000000000002000000000090.001111TESTERRORMESSAGE..' \
                       f'...........................................................................................' \
                       f'.........................................CGI\n'

    feedback_file_name = f'FEEDBACK.{file_ref}'

    with open(feedback_file_name, 'a+') as jv_file:
        jv_file.write(feedback_content)
        jv_file.close()

    # Now upload the ACK file to minio and publish message.
    with open(feedback_file_name, 'rb') as f:
        upload_to_minio(f.read(), feedback_file_name)
    # upload_to_minio(file_name=feedback_file_name, value_as_bytes=feedback_content.encode())

    await helper_add_ejv_event_to_queue(events_stan, file_name=feedback_file_name, message_type='FEEDBACKReceived')

    # Query EJV File and assert the status is changed
    ejv_file = EjvFileModel.find_by_id(ejv_file_id)
    assert ejv_file.disbursement_status_code == DisbursementStatus.ERRORED.value
    invoice = InvoiceModel.find_by_id(invoice.id)
    assert invoice.disbursement_status_code == DisbursementStatus.ERRORED.value
    disbursement_distribution_code = DistributionCodeModel.find_by_id(disbursement_distribution_code_id)
    assert disbursement_distribution_code.stop_ejv
