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
"""Task to create Journal Voucher for gov account payments."""

import time
from typing import List

from flask import current_app
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import EjvInvoiceLink as EjvInvoiceLinkModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import db
from pay_api.utils.enums import DisbursementStatus, EjvFileType, InvoiceReferenceStatus, InvoiceStatus, PaymentMethod
from pay_api.utils.util import generate_transaction_number

from tasks.common.cgi_ejv import CgiEjv
from utils.date import is_holiday


class EjvPaymentTask(CgiEjv):
    """Task to create Journal Voucher for gov account payments."""

    @classmethod
    def create_ejv_file(cls):
        """Create JV files and uplaod to CGI.

        Steps:
        1. Find all accounts for GI or GA.
        2. Find outstanding invoices for payment.
        3. Group by account and create JD for each service fee and filing fee.
        4. Upload the file to minio for future reference.
        5. Upload to sftp for processing. First upload JV file and then a TRG file.
        6. Update the statuses and create records to for the batch.
        """
        if is_holiday():
            current_app.logger.info('Deferring ejv payment task for another day.')
            return

        cls._create_ejv_file_for_gov_account(batch_type='GI')
        cls._create_ejv_file_for_gov_account(batch_type='GA')

    @classmethod
    def _create_ejv_file_for_gov_account(cls, batch_type: str):  # pylint:disable=too-many-locals, too-many-statements
        """Create EJV file for the partner and upload."""
        ejv_content: str = ''
        batch_total: float = 0
        control_total: int = 0

        # Create a ejv file model record.
        ejv_file_model: EjvFileModel = EjvFileModel(
            file_type=EjvFileType.PAYMENT.value,
            file_ref=cls.get_file_name(),
            disbursement_status_code=DisbursementStatus.UPLOADED.value
        ).flush()
        batch_number = cls.get_batch_number(ejv_file_model.id)

        # Get all invoices which should be part of the batch type.
        account_ids = cls._get_account_ids_for_payment(batch_type)

        # JV Batch Header
        batch_header: str = cls.get_batch_header(batch_number, batch_type)

        current_app.logger.info('Processing accounts.')
        for account_id in account_ids:
            account_jv: str = ''
            # Find all invoices for the gov account to pay.
            invoices = cls._get_invoices_for_payment(account_id)
            pay_account: PaymentAccountModel = PaymentAccountModel.find_by_id(account_id)
            # If no invoices continue.
            if not invoices or not pay_account.billable:
                continue

            disbursement_desc = f'{pay_account.name[:100]:<100}'
            effective_date: str = cls.get_effective_date()
            # Construct journal name
            ejv_header_model: EjvFileModel = EjvHeaderModel(
                payment_account_id=account_id,
                disbursement_status_code=DisbursementStatus.UPLOADED.value,
                ejv_file_id=ejv_file_model.id
            ).flush()
            journal_name: str = cls.get_journal_name(ejv_header_model.id)
            # Distribution code for the account.
            debit_distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_active_for_account(
                account_id
            )
            debit_distribution = cls.get_distribution_string(debit_distribution_code)  # Debit from GOV account GL

            line_number: int = 0
            total: float = 0
            current_app.logger.info(f'Processing invoices for account_id: {account_id}.')
            for inv in invoices:
                # If it's a JV reversal credit and debit is reversed.
                is_jv_reversal = inv.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value

                # If it's reversal, If there is no COMPLETED invoice reference, then no need to reverse it.
                # Else mark it as CANCELLED, as new invoice reference will be created
                if is_jv_reversal:
                    if (inv_ref := InvoiceReferenceModel.find_by_invoice_id_and_status(
                        inv.id, InvoiceReferenceStatus.COMPLETED.value
                    )) is None:
                        continue
                    inv_ref.status_code = InvoiceReferenceStatus.CANCELLED.value

                line_items = inv.payment_line_items

                for line in line_items:
                    # Line can have 2 distribution, 1 for the total and another one for service fees.
                    line_distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_id(
                        line.fee_distribution_id)
                    if line.total > 0:
                        total += line.total
                        line_distribution = cls.get_distribution_string(line_distribution_code)
                        flow_through = f'{line.invoice_id:<110}'
                        # Credit to BCREG GL
                        line_number += 1
                        control_total += 1
                        # If it's normal payment then the Line distribution goes as Credit,
                        # else it goes as Debit as we need to debit the fund from BC registry GL.
                        account_jv = account_jv + cls.get_jv_line(batch_type, line_distribution, disbursement_desc,
                                                                  effective_date, flow_through, journal_name,
                                                                  line.total,
                                                                  line_number, 'C' if not is_jv_reversal else 'D')

                        # Debit from GOV ACCOUNT GL
                        line_number += 1
                        control_total += 1
                        # If it's normal payment then the Gov account GL goes as Debit,
                        # else it goes as Credit as we need to credit the fund back to ministry.
                        account_jv = account_jv + cls.get_jv_line(batch_type, debit_distribution, disbursement_desc,
                                                                  effective_date, flow_through, journal_name,
                                                                  line.total,
                                                                  line_number, 'D' if not is_jv_reversal else 'C')
                    if line.service_fees > 0:
                        service_fee_distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_id(
                            line_distribution_code.service_fee_distribution_code_id)
                        total += line.service_fees
                        service_fee_distribution = cls.get_distribution_string(service_fee_distribution_code)
                        flow_through = f'{line.invoice_id:<110}'
                        # Credit to BCREG GL
                        line_number += 1
                        control_total += 1
                        account_jv = account_jv + cls.get_jv_line(batch_type, service_fee_distribution,
                                                                  disbursement_desc,
                                                                  effective_date, flow_through, journal_name,
                                                                  line.service_fees,
                                                                  line_number, 'C' if not is_jv_reversal else 'D')

                        # Debit from GOV ACCOUNT GL
                        line_number += 1
                        control_total += 1
                        account_jv = account_jv + cls.get_jv_line(batch_type, debit_distribution, disbursement_desc,
                                                                  effective_date, flow_through, journal_name,
                                                                  line.service_fees,
                                                                  line_number, 'D' if not is_jv_reversal else 'C')
            batch_total += total

            # Skip if we have no total from the invoices.
            if total > 0:
                # A JV header for each account.
                control_total += 1
                account_jv = cls.get_jv_header(batch_type, cls.get_journal_batch_name(batch_number),
                                               journal_name, total) + account_jv
                ejv_content = ejv_content + account_jv

            # Create ejv invoice link records and set invoice status
            current_app.logger.info('Creating ejv invoice link records and setting invoice status.')
            for inv in invoices:
                current_app.logger.debug(f'Creating EJV Invoice Link for invoice id: {inv.id}')
                # Create Ejv file link and flush
                ejv_invoice_link = EjvInvoiceLinkModel(invoice_id=inv.id, ejv_header_id=ejv_header_model.id,
                                                       disbursement_status_code=DisbursementStatus.UPLOADED.value)
                db.session.add(ejv_invoice_link)
                # Set distribution status to invoice
                # Create invoice reference record
                current_app.logger.debug(f'Creating Invoice Reference for invoice id: {inv.id}')
                inv_ref = InvoiceReferenceModel(
                    invoice_id=inv.id,
                    invoice_number=generate_transaction_number(inv.id),
                    reference_number=None,
                    status_code=InvoiceReferenceStatus.ACTIVE.value
                )
                db.session.add(inv_ref)
            db.session.flush()  # Instead of flushing every entity, flush all at once.

        if not ejv_content:
            db.session.rollback()
            return

        # JV Batch Trailer
        batch_trailer: str = cls.get_batch_trailer(batch_number, batch_total, batch_type, control_total)

        ejv_content = f'{batch_header}{ejv_content}{batch_trailer}'

        # Create a file add this content.
        file_path_with_name, trg_file_path = cls.create_inbox_and_trg_files(ejv_content)

        current_app.logger.info('Uploading to ftp.')

        # Upload file and trg to FTP
        cls.upload(ejv_content, cls.get_file_name(), file_path_with_name, trg_file_path)

        # commit changes to DB
        db.session.commit()

        # Add a sleep to prevent collision on file name.
        time.sleep(1)

    @classmethod
    def _get_account_ids_for_payment(cls, batch_type) -> List[int]:
        """Return account IDs for payment."""
        # CREDIT : Distribution code against fee schedule
        # DEBIT : Distribution code against account.
        bc_reg_client_code = current_app.config.get('CGI_BCREG_CLIENT_CODE')  # 112 #TODO
        query = db.session.query(DistributionCodeModel.account_id) \
            .filter(DistributionCodeModel.stop_ejv.is_(False) | DistributionCodeModel.stop_ejv.is_(None)) \
            .filter(DistributionCodeModel.account_id.isnot(None))

        if batch_type == 'GA':
            # Rule for GA. Credit is 112 and debit is 112. For BCREG client code is 112
            account_ids: List[int] = query.filter(DistributionCodeModel.client == bc_reg_client_code).all()
        else:
            # Rule for GI. Credit is 112 and debit is not 112. For BCREG client code is 112
            account_ids: List[int] = query.filter(DistributionCodeModel.client != bc_reg_client_code).all()
        return account_ids

    @classmethod
    def _get_invoices_for_payment(cls, account_id: int) -> List[InvoiceModel]:
        """Return invoices for payments."""
        valid_statuses = (InvoiceStatus.APPROVED.value, InvoiceStatus.REFUND_REQUESTED.value)
        invoice_ref_subquery = db.session.query(InvoiceReferenceModel.invoice_id). \
            filter(InvoiceReferenceModel.status_code.in_((InvoiceReferenceStatus.ACTIVE.value,)))

        invoices: List[InvoiceModel] = db.session.query(InvoiceModel) \
            .filter(InvoiceModel.invoice_status_code.in_(valid_statuses)) \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EJV.value) \
            .filter(InvoiceModel.payment_account_id == account_id) \
            .filter(InvoiceModel.id.notin_(invoice_ref_subquery)) \
            .all()
        return invoices
