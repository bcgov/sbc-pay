# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Task to create Journal Voucher."""

import os
import tempfile
import time
from datetime import datetime
from typing import List

from flask import current_app
from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import EjvInvoiceLink as EjvInvoiceLinkModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import db
from pay_api.utils.enums import DisbursementStatus, InvoiceStatus
from pay_api.utils.util import get_fiscal_year, get_nearest_business_day

from utils.minio import put_object
from utils.sftp import upload_to_ftp

DELIMITER = chr(29)  # '<0x1d>'
EMPTY = ''


class CgiEjvTask:  # pylint:disable=too-many-locals, too-many-statements, too-few-public-methods
    """Task to create EJV Files."""

    @classmethod
    def create_ejv_file(cls):
        """Create JV files and uplaod to CGI.

        Steps:
        1. Find all invoices from invoice table for disbursements.
        2. Group by fee schedule and create JV Header and JV Details.
        3. Upload the file to minio for future reference.
        4. Upload to sftp for processing. First upload JV file and then a TRG file.
        5. Update the statuses and create records to for the batch.
        """
        cls._create_ejv_file_for_partner(batch_type='GI')  # Internal ministry
        cls._create_ejv_file_for_partner(batch_type='GA')  # External ministry

    @classmethod
    def _create_ejv_file_for_partner(cls, batch_type: str):
        """Create EJV file for the partner and upload."""
        ejv_content: str = ''
        batch_total: float = 0
        control_total: int = 0
        today = datetime.now()
        disbursement_desc = current_app.config.get('CGI_DISBURSEMENT_DESC'). \
            format(today.strftime('%B').upper(), f'{today.day:0>2}')[:100]
        disbursement_desc = f'{disbursement_desc:<100}'
        message_version = current_app.config.get('CGI_MESSAGE_VERSION')
        fiscal_year = get_fiscal_year(today)
        feeder_number = current_app.config.get('CGI_FEEDER_NUMBER')
        ministry = current_app.config.get('CGI_MINISTRY_PREFIX')
        trg_suffix = current_app.config.get('CGI_TRIGGER_FILE_SUFFIX')

        # Create file name
        date_time = get_nearest_business_day(datetime.now()).strftime('%Y%m%d%H%M%S')
        file_name: str = f'INBOX.F{feeder_number}.{date_time}'
        current_app.logger.info('file_name %s', file_name)

        # Create Batch Header.
        # Create a ejv file model record.
        ejv_file_model: EjvFileModel = EjvFileModel(
            is_distribution=True,
            file_ref=file_name,
            disbursement_status_code=DisbursementStatus.UPLOADED.value
        ).flush()
        batch_number = f'{ejv_file_model.id:0>9}'
        journal_batch_name: str = f'{ministry}{batch_number}{EMPTY:<14}'

        # Get partner list. Each of the partner will go as a JV Header and transactions as JV Details.
        partners: List[CorpTypeModel] = db.session.query(CorpTypeModel.code)\
            .filter(CorpTypeModel.batch_type == batch_type).all()

        # JV Batch Header
        batch_header: str = f'{feeder_number}{batch_type}BH{DELIMITER}{feeder_number}{fiscal_year}' \
                            f'{batch_number}{message_version}{DELIMITER}{os.linesep}'

        for partner in partners:
            # Find all invoices for the partner to disburse.
            invoices = cls._get_invoices_for_disbursement(partner)
            # If no invoices continue.
            if not invoices:
                continue

            effective_date: str = cls._get_effective_date()
            # Construct journal name
            ejv_header_model: EjvFileModel = EjvHeaderModel(
                partner_code=partner.code,
                disbursement_status_code=DisbursementStatus.UPLOADED.value,
                ejv_file_id=ejv_file_model.id
            ).flush()
            journal_name: str = f'{ministry}{ejv_header_model.id:0>8}'

            # To populate JV Header and JV Details, group these invoices by the distribution
            # and create one JV Header and detail for each.
            distribution_code_set = set()
            invoice_id_list = []
            for inv in invoices:
                invoice_id_list.append(inv.id)
                # Create Ejv file link and flush
                EjvInvoiceLinkModel(invoice_id=inv.id, ejv_header_id=ejv_header_model.id).flush()
                # Set distribution status to invoice
                inv.disbursement_status_code = DisbursementStatus.UPLOADED.value
                inv.flush()
                for line_item in inv.payment_line_items:
                    distribution_code_set.add(line_item.fee_distribution_id)

            for distribution_code_id in list(distribution_code_set):
                distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_id(distribution_code_id)
                line_items = cls._find_line_items_by_invoice_and_distribution(distribution_code_id, invoice_id_list)

                total: float = 0
                for line in line_items:
                    total += line.total

                batch_total += total

                debit_distribution = cls._get_distribution_string(distribution_code)  # Debit from BCREG GL
                credit_distribution_code = DistributionCodeModel.find_by_id(
                    distribution_code.disbursement_distribution_code_id
                )
                credit_distribution = cls._get_distribution_string(credit_distribution_code)  # Credit to partner GL

                # JV Header
                ejv_content = f'{ejv_content}{feeder_number}{batch_type}JH{DELIMITER}{journal_name}' \
                              f'{journal_batch_name}{cls._format_amount(total)}ACAD{EMPTY:<100}{EMPTY:<110}' \
                              f'{DELIMITER}{os.linesep}'

                line_number: int = 0
                for line in line_items:
                    # JV Details
                    line_number += 1
                    # Line for credit.
                    ejv_content = f'{ejv_content}{feeder_number}{batch_type}JD{DELIMITER}{journal_name}' \
                                  f'{line_number:0>5}{effective_date}{credit_distribution}{EMPTY:<9}' \
                                  f'{cls._format_amount(line.total)}C{disbursement_desc}{EMPTY:<110}' \
                                  f'{DELIMITER}{os.linesep}'
                    line_number += 1
                    # Add a line here for debit too
                    ejv_content = f'{ejv_content}{feeder_number}{batch_type}JD{DELIMITER}{journal_name}' \
                                  f'{line_number:0>5}{effective_date}{debit_distribution}{EMPTY:<9}' \
                                  f'{cls._format_amount(line.total)}D{disbursement_desc}{EMPTY:<110}' \
                                  f'{DELIMITER}{os.linesep}'

                    control_total += 1
        if not ejv_content:
            db.session.rollback()
            return

        # JV Batch Trailer
        batch_trailer: str = f'{feeder_number}{batch_type}BT{DELIMITER}{feeder_number}{fiscal_year}{batch_number}' \
                             f'{control_total:0>15}{cls._format_amount(batch_total)}{DELIMITER}{os.linesep}'

        ejv_content = f'{batch_header}{ejv_content}{batch_trailer}'
        # Create a file add this content.
        file_path: str = tempfile.gettempdir()
        file_path_with_name = f'{file_path}/{file_name}'
        trg_file_path = f'{file_path_with_name}.{trg_suffix}'
        with open(file_path_with_name, 'a+') as jv_file:
            jv_file.write(ejv_content)
            jv_file.close()

        # TRG File
        with open(trg_file_path, 'a+') as trg_file:
            trg_file.write('')
            trg_file.close()

        # Upload file and trg to FTP
        upload_to_ftp(file_path_with_name, trg_file_path)

        # Upload to MINIO
        cls._upload_to_minio(content=ejv_content.encode(),
                             file_name=file_name,
                             file_size=os.stat(file_path_with_name).st_size)

        # commit changes to DB
        db.session.commit()

        # Add a sleep to prevent collision on file name.
        time.sleep(1)

    @classmethod
    def _find_line_items_by_invoice_and_distribution(cls, distribution_code_id, invoice_id_list):
        """Find and return all payment line items for this distribution."""
        line_items: List[PaymentLineItemModel] = db.session.query(PaymentLineItemModel) \
            .filter(PaymentLineItemModel.invoice_id.in_(invoice_id_list)) \
            .filter(PaymentLineItemModel.fee_distribution_id == distribution_code_id)
        return line_items

    @classmethod
    def _get_invoices_for_disbursement(cls, partner):
        """Return invoices for disbursement."""
        invoices: List[InvoiceModel] = db.session.query(InvoiceModel) \
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value) \
            .filter((InvoiceModel.disbursement_status_code.is_(None)) |
                    (InvoiceModel.disbursement_status_code == DisbursementStatus.ERRORED.value)) \
            .filter(InvoiceModel.corp_type_code == partner.code) \
            .all()
        return invoices

    @classmethod
    def _get_distribution_string(cls, dist_code: DistributionCodeModel):
        """Return GL code combination for the distribution."""
        return f'{dist_code.client}{dist_code.responsibility_centre}{dist_code.service_line}' \
               f'{dist_code.stob}{dist_code.project_code}0000000000{EMPTY:<16}'

    @classmethod
    def _get_effective_date(cls):
        """Return effective date.."""
        # TODO Use current date now, need confirmation
        return get_nearest_business_day(datetime.now()).strftime('%Y%m%d')

    @classmethod
    def _format_amount(cls, amount: float):
        """Format and return amount to fix 2 decimal places and total of length 15 prefixed with zeroes."""
        formatted_amount: str = f'{amount:.2f}'
        return formatted_amount.zfill(15)

    @classmethod
    def _upload_to_minio(cls, content, file_name, file_size):
        """Upload to minio."""
        try:
            put_object(content, file_name, file_size)
        except Exception as e:  # NOQA # pylint: disable=broad-except
            current_app.logger.error(e)
            current_app.logger.error(f'upload to minio failed for the file: {file_name}')
