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
"""EJV reconciliation file.

The entry-point is the **cb_subscription_handler**

The design and flow leverage a few constraints that are placed upon it
by NATS Streaming and using AWAIT on the default loop.
- NATS streaming queues require one message to be processed at a time.
- AWAIT on the default loop effectively runs synchronously

If these constraints change, the use of Flask-SQLAlchemy would need to change.
Flask-SQLAlchemy currently allows the base model to be changed, or reworking
the model to a standalone SQLAlchemy usage with an async engine would need
to be pursued.
"""
import os
from datetime import datetime
from typing import Dict, List, Optional

from entity_queue_common.service_utils import logger
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import EjvInvoiceLink as EjvInvoiceLinkModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import db
from pay_api.services.queue_publisher import publish
from pay_api.utils.enums import (
    DisbursementStatus, EjvFileType, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus, PaymentSystem)
from sentry_sdk import capture_message

from reconciliations import config
from reconciliations.minio import get_object


APP_CONFIG = config.get_named_config(os.getenv('DEPLOYMENT_ENV', 'production'))


async def reconcile_distributions(msg: Dict[str, any], is_feedback: bool = False):
    """Read the file and update distribution details.

    1: Lookup the invoice details based on the file content.
    2: Update the statuses
    """
    if is_feedback:
        await _update_feedback(msg)
    else:
        _update_acknowledgement()


def _update_acknowledgement():
    # As per documentation, feedback file is timestamped by the date time when it is picked,
    # so query uploaded jv file records and mark it as acknowledged.

    ejv_file: EjvFileModel = db.session.query(EjvFileModel).filter(
        EjvFileModel.disbursement_status_code == DisbursementStatus.UPLOADED.value).one_or_none()
    ejv_headers: List[EjvHeaderModel] = db.session.query(EjvHeaderModel).filter(
        EjvHeaderModel.ejv_file_id == ejv_file.id).all()

    ejv_file.disbursement_status_code = DisbursementStatus.ACKNOWLEDGED.value

    for ejv_header in ejv_headers:
        ejv_header.disbursement_status_code = DisbursementStatus.ACKNOWLEDGED.value
        if ejv_file.file_type == EjvFileType.DISBURSEMENT.value:
            ejv_links: List[EjvInvoiceLinkModel] = db.session.query(EjvInvoiceLinkModel).filter(
                EjvInvoiceLinkModel.ejv_header_id == ejv_header.id).all()
            for ejv_link in ejv_links:
                invoice: InvoiceModel = InvoiceModel.find_by_id(ejv_link.invoice_id)
                invoice.disbursement_status_code = DisbursementStatus.ACKNOWLEDGED.value
    db.session.commit()


async def _update_feedback(msg: Dict[str, any]):  # pylint:disable=too-many-locals, too-many-statements
    # Read the file and find records from the database, and update status.
    has_errors: bool = False
    file_name: str = msg.get('data').get('fileName')
    minio_location: str = msg.get('data').get('location')
    file = get_object(minio_location, file_name)
    content = file.data.decode('utf-8-sig')
    group_batches: List[str] = _group_batches(content)
    for group_batch in group_batches:
        ejv_file: Optional[EjvFileModel] = None
        receipt_number: Optional[str] = None
        for line in group_batch.splitlines():
            # For all these indexes refer the sharepoint docs refer : https://github.com/bcgov/entity/issues/6226
            is_batch_group: bool = line[2:4] == 'BG'
            is_batch_header: bool = line[2:4] == 'BH'
            is_jv_header: bool = line[2:4] == 'JH'
            is_jv_detail: bool = line[2:4] == 'JD'
            if is_batch_group:
                batch_number = int(line[15:24])
                ejv_file = EjvFileModel.find_by_id(batch_number)
            elif is_batch_header:
                return_code = line[7:11]
                return_message = line[11:161]
                ejv_file.disbursement_status_code = _get_disbursement_status(return_code)
                ejv_file.message = return_message
                if ejv_file.disbursement_status_code == DisbursementStatus.ERRORED.value:
                    has_errors = True
            elif is_jv_header:
                journal_name: str = line[7:17]  # {ministry}{ejv_header_model.id:0>8}
                ejv_header_model_id = int(journal_name[2:])
                ejv_header: EjvHeaderModel = EjvHeaderModel.find_by_id(ejv_header_model_id)
                ejv_header_return_code = line[271:275]
                ejv_header.disbursement_status_code = _get_disbursement_status(ejv_header_return_code)
                ejv_header_error_message = line[275:425]
                ejv_header.message = ejv_header_error_message
                if ejv_header.disbursement_status_code == DisbursementStatus.ERRORED.value:
                    has_errors = True
                # Create a payment record if its a gov account payment.
                elif ejv_file.file_type == EjvFileType.PAYMENT.value:
                    amount = float(line[42:57])
                    receipt_number = line[0:42].strip()
                    await _create_payment_record(amount, ejv_header, receipt_number)

            elif is_jv_detail:
                has_errors = await _process_jv_details_feedback(ejv_file, has_errors, line, receipt_number)

    if has_errors:
        await _publish_mailer_events(file_name, minio_location)

    db.session.commit()


async def _process_jv_details_feedback(ejv_file, has_errors, line, receipt_number):  # pylint:disable=too-many-locals
    journal_name: str = line[7:17]  # {ministry}{ejv_header_model.id:0>8}
    ejv_header_model_id = int(journal_name[2:])
    invoice_id = int(line[205:315])
    invoice: InvoiceModel = InvoiceModel.find_by_id(invoice_id)
    invoice_link: EjvInvoiceLinkModel = db.session.query(EjvInvoiceLinkModel).filter(
        EjvInvoiceLinkModel.ejv_header_id == ejv_header_model_id).filter(
        EjvInvoiceLinkModel.invoice_id == invoice_id).one_or_none()
    invoice_return_code = line[315:319]
    invoice_return_message = line[319:469]
    # If the JV process failed, then mark the GL code against the invoice to be stopped
    # for further JV process for the credit GL.
    logger.info('Is Credit or Debit %s - %s', line[104:105], ejv_file.file_type)
    if line[104:105] == 'C' and ejv_file.file_type == EjvFileType.DISBURSEMENT.value:
        disbursement_status = _get_disbursement_status(invoice_return_code)
        invoice_link.disbursement_status_code = disbursement_status
        invoice_link.message = invoice_return_message
        logger.info('disbursement_status %s', disbursement_status)
        if disbursement_status == DisbursementStatus.ERRORED.value:
            has_errors = True
            invoice.disbursement_status_code = DisbursementStatus.ERRORED.value
            line_items: List[PaymentLineItemModel] = invoice.payment_line_items
            for line_item in line_items:
                # Line debit distribution
                debit_distribution: DistributionCodeModel = DistributionCodeModel \
                    .find_by_id(line_item.fee_distribution_id)
                credit_distribution: DistributionCodeModel = DistributionCodeModel \
                    .find_by_id(debit_distribution.disbursement_distribution_code_id)
                credit_distribution.stop_ejv = True
        else:
            await _update_invoice_status(invoice)

    elif line[104:105] == 'D' and ejv_file.file_type == EjvFileType.PAYMENT.value:
        # This is for gov account payment JV.
        invoice_link.disbursement_status_code = _get_disbursement_status(invoice_return_code)

        invoice_link.message = invoice_return_message
        logger.info('Invoice ID %s', invoice_id)
        inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_reference_by_invoice_id_and_status(
            invoice_id, InvoiceReferenceStatus.ACTIVE.value)
        logger.info('invoice_link.disbursement_status_code %s', invoice_link.disbursement_status_code)
        if invoice_link.disbursement_status_code == DisbursementStatus.ERRORED.value:
            has_errors = True
            # Cancel the invoice reference.
            if inv_ref:
                inv_ref.status_code = InvoiceReferenceStatus.CANCELLED.value
            # Find the distribution code and set the stop_ejv flag to TRUE
            dist_code: DistributionCodeModel = DistributionCodeModel.find_by_active_for_account(
                invoice.payment_account_id)
            dist_code.stop_ejv = True
        elif invoice_link.disbursement_status_code == DisbursementStatus.COMPLETED.value:
            # Set the invoice status as REFUNDED if it's a JV reversal, else mark as PAID
            is_reversal = invoice.invoice_status_code in (
                InvoiceStatus.REFUNDED.value, InvoiceStatus.REFUND_REQUESTED.value)

            invoice.invoice_status_code = InvoiceStatus.REFUNDED.value if is_reversal else InvoiceStatus.PAID.value

            # Mark the invoice reference as COMPLETED, create a receipt
            if inv_ref:
                inv_ref.status_code = InvoiceReferenceStatus.COMPLETED.value
            # Find receipt and add total to it, as single invoice can be multiple rows in the file
            if not is_reversal:
                receipt = ReceiptModel.find_by_invoice_id_and_receipt_number(invoice_id=invoice_id,
                                                                             receipt_number=receipt_number)
                if receipt:
                    receipt.receipt_amount += float(line[89:104])
                else:
                    ReceiptModel(invoice_id=invoice_id, receipt_number=receipt_number, receipt_date=datetime.now(),
                                 receipt_amount=float(line[89:104])).flush()
    return has_errors


async def _update_invoice_status(invoice):
    """Update status to reversed if its a refund, else to completed."""
    if invoice.invoice_status_code in (InvoiceStatus.REFUNDED.value, InvoiceStatus.REFUND_REQUESTED.value):
        invoice.disbursement_status_code = DisbursementStatus.REVERSED.value
    else:
        invoice.disbursement_status_code = DisbursementStatus.COMPLETED.value


async def _create_payment_record(amount, ejv_header, receipt_number):
    """Create payment record."""
    PaymentModel(
        payment_system_code=PaymentSystem.CGI.value,
        payment_account_id=ejv_header.payment_account_id,
        payment_method_code=PaymentMethod.EJV.value,
        payment_status_code=PaymentStatus.COMPLETED.value,
        receipt_number=receipt_number,
        invoice_amount=amount,
        paid_amount=amount,
        payment_date=datetime.now()).flush()


def _group_batches(content: str):
    """Group batches based on the group and trailer.."""
    # A batch starts from BG to BT.
    group_batches: List[str] = []
    batch_content: str = ''

    for line in content.splitlines():
        if line[2:4] == 'BG':  # batch starts from BG
            batch_content = line
        else:
            batch_content = batch_content + os.linesep + line
            if line[2:4] == 'BT':  # batch ends with BT
                group_batches.append(batch_content)

    return group_batches


def _get_disbursement_status(return_code: str) -> str:
    """Return disbursement status from return code."""
    if return_code == '0000':
        return DisbursementStatus.COMPLETED.value
    return DisbursementStatus.ERRORED.value


async def _publish_mailer_events(file_name: str, minio_location: str):
    """Publish payment message to the mailer queue."""
    # Publish message to the Queue, saying account has been created. Using the event spec.
    queue_data = {
        'fileName': file_name,
        'minioLocation': minio_location
    }
    payload = {
        'specversion': '1.x-wip',
        'type': 'bc.registry.payment.ejvFailed',
        'source': 'https://api.pay.bcregistry.gov.bc.ca/v1/accounts/',
        'id': file_name,
        'time': f'{datetime.now()}',
        'datacontenttype': 'application/json',
        'data': queue_data
    }

    try:
        await publish(payload=payload,
                      client_name=APP_CONFIG.NATS_MAILER_CLIENT_NAME,
                      subject=APP_CONFIG.NATS_MAILER_SUBJECT)
    except Exception as e:  # NOQA pylint: disable=broad-except
        logger.error(e)
        capture_message('EJV Failed message error', level='error')
