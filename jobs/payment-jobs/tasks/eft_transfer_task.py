# Copyright © 2023 Province of British Columbia
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
"""Task to create EFT Transfer Journal Voucher."""

import time
from datetime import datetime
from typing import List

from flask import current_app
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import EFTGLTransfer as EFTGLTransferModel
from pay_api.models import EFTShortnames as EFTShortnameModel
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import EjvInvoiceLink as EjvInvoiceLinkModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import db
from pay_api.services.flags import flags
from pay_api.utils.enums import DisbursementStatus, EFTGlTransferType, EjvFileType, InvoiceStatus, PaymentMethod
from sqlalchemy import exists, func

from tasks.common.cgi_ejv import CgiEjv


class EftTransferTask(CgiEjv):
    """Task to create EJV Files."""

    @classmethod
    def create_ejv_file(cls):
        """Create JV files and upload to CGI.

        Steps:
        1. Find all invoices from invoice table for EFT Transfer.
        2. Group by fee schedule and create JV Header and JV Details.
        3. Upload the file to minio for future reference.
        4. Upload to sftp for processing. First upload JV file and then a TRG file.
        5. Update the statuses and create records to for the batch.
        """
        eft_enabled = flags.is_on('enable-eft-payment-method', default=False)
        if eft_enabled:
            cls._create_ejv_file_for_eft_transfer()

    @staticmethod
    def get_invoices_for_transfer(payment_account_id: int):
        """Return invoices for EFT Holdings transfer."""
        # Return all EFT Paid invoices that don't already have an EFT GL Transfer record
        invoices: List[InvoiceModel] = db.session.query(InvoiceModel) \
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value) \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value) \
            .filter(InvoiceModel.payment_account_id == payment_account_id) \
            .filter(~exists().where((EFTGLTransferModel.invoice_id == InvoiceModel.id) &
                                    (EFTGLTransferModel.transfer_type == EFTGlTransferType.TRANSFER.value))).all()
        return invoices

    @staticmethod
    def get_invoices_for_refund_reversal(payment_account_id: int):
        """Return invoices for EFT reversal."""
        refund_inv_statuses = (InvoiceStatus.REFUNDED.value, InvoiceStatus.REFUND_REQUESTED.value,
                               InvoiceStatus.CREDITED.value)
        # Future may need to re-evaluate when EFT Short name unlinking use cases are defined
        invoices: List[InvoiceModel] = db.session.query(InvoiceModel) \
            .filter(InvoiceModel.invoice_status_code.in_(refund_inv_statuses)) \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value) \
            .filter(InvoiceModel.payment_account_id == payment_account_id) \
            .filter(InvoiceModel.disbursement_status_code == DisbursementStatus.COMPLETED.value) \
            .filter(~exists().where((EFTGLTransferModel.invoice_id == InvoiceModel.id) &
                                    (EFTGLTransferModel.transfer_type == EFTGlTransferType.REVERSAL.value))).all()
        current_app.logger.info(invoices)
        return invoices

    @staticmethod
    def get_account_ids() -> List[int]:
        """Return account IDs for EFT payments."""
        return db.session.query(func.DISTINCT(InvoiceModel.payment_account_id)) \
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value) \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value) \
            .filter(~exists().where((EFTGLTransferModel.invoice_id == InvoiceModel.id) &
                                    (EFTGLTransferModel.transfer_type == EFTGlTransferType.TRANSFER.value))).all()

    @staticmethod
    def create_eft_gl_transfer(eft_holding_gl: str, line_distribution_gl: str, transfer_type: str,
                               line_item: PaymentLineItemModel, payment_account: PaymentAccountModel):
        """Create EFT GL Transfer record."""
        short_name_id = db.session.query(EFTShortnameModel.id) \
            .filter(EFTShortnameModel.auth_account_id == payment_account.auth_account_id).one()
        source_gl = eft_holding_gl if transfer_type == EFTGlTransferType.TRANSFER.value else line_distribution_gl
        target_gl = line_distribution_gl if transfer_type == EFTGlTransferType.TRANSFER.value else eft_holding_gl
        now = datetime.now()
        return EFTGLTransferModel(
            invoice_id=line_item.invoice_id,
            is_processed=True,
            processed_on=now,
            short_name_id=short_name_id,
            source_gl=source_gl.strip(),
            target_gl=target_gl.strip(),
            transfer_amount=line_item.total,
            transfer_type=transfer_type,
            transfer_date=now
        )

    @classmethod
    def _process_eft_transfer_invoices(cls, invoices: [InvoiceModel], transfer_type: str,
                                       eft_gl_transfers: dict = None) -> [EFTGLTransferModel]:
        """Create EFT GL Transfer for invoice line items."""
        eft_holding_gl = current_app.config.get('EFT_HOLDING_GL')
        eft_gl_transfers = eft_gl_transfers or {}

        for invoice in invoices:
            payment_account = PaymentAccountModel.find_by_id(invoice.payment_account_id)
            for line_item in invoice.payment_line_items:
                distribution_code: DistributionCodeModel = \
                    DistributionCodeModel.find_by_id(line_item.fee_distribution_id)

                # Create line distribution transfer
                line_distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_id(
                    distribution_code.distribution_code_id
                )

                line_distribution = cls.get_distribution_string(line_distribution_code)

                line_gl_transfer = cls.create_eft_gl_transfer(
                    eft_holding_gl=eft_holding_gl,
                    line_distribution_gl=line_distribution,
                    transfer_type=transfer_type,
                    line_item=line_item,
                    payment_account=payment_account
                )

                eft_gl_transfers.setdefault(invoice.payment_account_id, [])
                eft_gl_transfers[invoice.payment_account_id].append(line_gl_transfer)
                db.session.add(line_gl_transfer)

                # Check for service fee, if there is one create a transfer record
                if distribution_code.service_fee_distribution_code_id:
                    service_fee_distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_id(
                        distribution_code.service_fee_distribution_code_id
                    )

                    service_fee_distribution = cls.get_distribution_string(service_fee_distribution_code)

                    service_fee_gl_transfer = cls.create_eft_gl_transfer(
                        eft_holding_gl=eft_holding_gl,
                        line_distribution_gl=service_fee_distribution,
                        transfer_type=transfer_type,
                        line_item=line_item,
                        payment_account=payment_account
                    )
                    service_fee_gl_transfer.transfer_amount = line_item.service_fees
                    eft_gl_transfers[invoice.payment_account_id].append(service_fee_gl_transfer)
                    db.session.add(service_fee_gl_transfer)

        return eft_gl_transfers

    @staticmethod
    def process_invoice_ejv_links(invoices: [InvoiceModel], ejv_header_model_id: int):
        """Create EJV Invoice Links."""
        current_app.logger.info('Creating ejv invoice link records and setting invoice status.')
        sequence = 1
        for inv in invoices:
            current_app.logger.debug(f'Creating EJV Invoice Link for invoice id: {inv.id}')
            # Create Ejv file link and flush
            ejv_invoice_link = EjvInvoiceLinkModel(invoice_id=inv.id, ejv_header_id=ejv_header_model_id,
                                                   disbursement_status_code=DisbursementStatus.UPLOADED.value,
                                                   sequence=sequence)
            db.session.add(ejv_invoice_link)
            sequence += 1

    @classmethod
    def _create_ejv_file_for_eft_transfer(cls):  # pylint:disable=too-many-locals, too-many-statements
        """Create EJV file for the EFT Transfer and upload."""
        ejv_content: str = ''
        batch_total: float = 0
        control_total: int = 0
        today = datetime.now()
        transfer_desc = current_app.config.get('EFT_TRANSFER_DESC'). \
            format(today.strftime('%B').upper(), f'{today.day:0>2}')[:100]
        transfer_desc = f'{transfer_desc:<100}'

        # Create a ejv file model record.
        ejv_file_model: EjvFileModel = EjvFileModel(
            file_type=EjvFileType.TRANSFER.value,
            file_ref=cls.get_file_name(),
            disbursement_status_code=DisbursementStatus.UPLOADED.value
        ).flush()
        batch_number = cls.get_batch_number(ejv_file_model.id)
        batch_type = 'GA'

        account_ids = cls.get_account_ids()

        # JV Batch Header
        batch_header: str = cls.get_batch_header(batch_number, batch_type)

        effective_date: str = cls.get_effective_date()
        for account_id in account_ids:
            account_jv: str = ''
            payment_invoices = cls.get_invoices_for_transfer(account_id)
            refund_invoices = cls.get_invoices_for_refund_reversal(account_id)
            transfers = cls._process_eft_transfer_invoices(payment_invoices, EFTGlTransferType.TRANSFER.value)
            cls._process_eft_transfer_invoices(refund_invoices, EFTGlTransferType.REVERSAL.value, transfers)
            invoices = payment_invoices + refund_invoices

            ejv_header_model: EjvFileModel = EjvHeaderModel(
                payment_account_id=account_id,
                disbursement_status_code=DisbursementStatus.UPLOADED.value,
                ejv_file_id=ejv_file_model.id
            ).flush()
            journal_name: str = cls.get_journal_name(ejv_header_model.id)

            line_number: int = 0
            total: float = 0

            current_app.logger.info(f'Processing EFT Transfers for account_id: {account_id}.')
            account_transfers: List[EFTGLTransferModel] = transfers[account_id[0]]

            for eft_transfer in account_transfers:
                invoice_number = f'#{eft_transfer.invoice_id}'
                description = transfer_desc[:-len(invoice_number)] + invoice_number
                description = f'{description[:100]:<100}'

                if eft_transfer.transfer_amount > 0:
                    total += eft_transfer.transfer_amount
                    flow_through = f'{eft_transfer.invoice_id:<110}'

                    line_number += 1
                    control_total += 1

                    # Debit from source gl
                    source_gl = f'{eft_transfer.source_gl}{cls.EMPTY:<16}'
                    target_gl = f'{eft_transfer.target_gl}{cls.EMPTY:<16}'

                    account_jv = account_jv + cls.get_jv_line(batch_type, source_gl, description,
                                                              effective_date, flow_through, journal_name,
                                                              eft_transfer.transfer_amount,
                                                              line_number, 'D')
                    # Credit to target gl
                    account_jv = account_jv + cls.get_jv_line(batch_type, target_gl, description,
                                                              effective_date, flow_through, journal_name,
                                                              eft_transfer.transfer_amount,
                                                              line_number, 'C')
                    line_number += 1
                    control_total += 1

            batch_total += total

            # Skip if we have no total from the transfers.
            if total > 0:
                # A JV header for each account.
                control_total += 1
                account_jv = cls.get_jv_header(batch_type, cls.get_journal_batch_name(batch_number),
                                               journal_name, total) + account_jv
                ejv_content = ejv_content + account_jv

            # Create ejv invoice link records and set invoice status
            cls.process_invoice_ejv_links(invoices, ejv_header_model.id)

            db.session.flush()

        if not ejv_content:
            db.session.rollback()
            return

        # JV Batch Trailer
        batch_trailer: str = cls.get_batch_trailer(batch_number, batch_total, batch_type, control_total)
        ejv_content = f'{batch_header}{ejv_content}{batch_trailer}'

        # Create a file add this content.
        file_path_with_name, trg_file_path = cls.create_inbox_and_trg_files(ejv_content)

        # Upload file and trg to FTP
        current_app.logger.info('Uploading EFT Transfer file to ftp.')
        cls.upload(ejv_content, cls.get_file_name(), file_path_with_name, trg_file_path)

        db.session.commit()

        # Add a sleep to prevent collision on file name.
        time.sleep(1)
