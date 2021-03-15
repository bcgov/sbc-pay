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
from typing import Dict, List

from entity_queue_common.service_utils import logger
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import EjvInvoiceLink as EjvInvoiceLinkModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import db
from pay_api.services.queue_publisher import publish
from pay_api.utils.enums import DisbursementStatus
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
        ejv_links: List[EjvInvoiceLinkModel] = db.session.query(EjvInvoiceLinkModel).filter(
            EjvInvoiceLinkModel.ejv_header_id == ejv_header.id).all()
        for ejv_link in ejv_links:
            invoice: InvoiceModel = InvoiceModel.find_by_id(ejv_link.invoice_id)
            invoice.disbursement_status_code = DisbursementStatus.ACKNOWLEDGED.value


async def _update_feedback(msg: Dict[str, any]):  # pylint:disable=too-many-locals
    # Read the file and find records from the database, and update status.
    file_name: str = msg.get('data').get('fileName')
    minio_location: str = msg.get('data').get('location')
    file = get_object(minio_location, file_name)
    content = file.data.decode('utf-8-sig')

    ejv_file: EjvFileModel = None
    for line in content.splitlines():
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
            await _publish_mailer_events(file_name, minio_location)
        elif is_jv_header:
            journal_name: str = line[7:17]  # {ministry}{ejv_header_model.id:0>8}
            ejv_header_model_id = int(journal_name[2:])
            ejv_header: EjvHeaderModel = EjvHeaderModel.find_by_id(ejv_header_model_id)
            ejv_header_return_code = line[271:275]
            ejv_header.disbursement_status_code = _get_disbursement_status(ejv_header_return_code)
            ejv_header_error_message = line[275:425]
            ejv_header.message = ejv_header_error_message
        elif is_jv_detail:
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
            is_credit: bool = line[104:105] == 'C'
            if is_credit:
                invoice_link.disbursement_status_code = _get_disbursement_status(invoice_return_code)
                invoice_link.message = invoice_return_message
                invoice.disbursement_status_code = _get_disbursement_status(invoice_return_code)

                line_items: List[PaymentLineItemModel] = invoice.payment_line_items
                for line_item in line_items:
                    # Line debit distribution
                    debit_distribution: DistributionCodeModel = DistributionCodeModel \
                        .find_by_id(line_item.fee_distribution_id)
                    credit_distribution: DistributionCodeModel = DistributionCodeModel \
                        .find_by_id(debit_distribution.disbursement_distribution_code_id)
                    credit_distribution.stop_ejv = True

    db.session.commit()


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
