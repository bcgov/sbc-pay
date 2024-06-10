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

import time
from datetime import datetime, timedelta
import pytz 
from typing import List

from flask import current_app
from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import DistributionCodeLink as DistributionCodeLinkModel
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import EjvLink as EjvLinkModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import RefundsPartial as RefundsPartialModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import db
from pay_api.utils.enums import DisbursementStatus, EjvFileType, EJVLinkType, InvoiceStatus, PaymentMethod
from sqlalchemy import Date, cast

from tasks.common.cgi_ejv import CgiEjv


pst_timezone = pytz.utc.localize('Canada/Pacific')
now_naive = datetime()
now_aware = pytz.utc.localize(now_naive)
pst_time = now_aware.astimezone(pst_timezone)

class EjvPartnerDistributionTask(CgiEjv):
    """Task to create EJV Files."""

    @classmethod
    def create_ejv_file(cls):
        """Create JV files and upload to CGI.

        Steps:
        1. Find all invoices from invoice table for disbursements.
        2. Group by fee schedule and create JV Header and JV Details.
        3. Upload the file to minio for future reference.
        4. Upload to sftp for processing. First upload JV file and then a TRG file.
        5. Update the statuses and create records to for the batch.
        """
        cls._create_ejv_file_for_partner(batch_type='GI')  # Internal ministry
        cls._create_ejv_file_for_partner(batch_type='GA')  # External ministry

    @staticmethod
    def get_invoices_for_disbursement(partner):
        """Return invoices for disbursement. Used by EJV and AP."""
        #disbursement_date = datetime.today() - timedelta(days=current_app.config.get('DISBURSEMENT_DELAY_IN_DAYS'))
        disbursement_date = pst_time - timedelta(days=current_app.config.get('DISBURSEMENT_DELAY_IN_DAYS'))
        invoices: List[InvoiceModel] = db.session.query(InvoiceModel) \
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value) \
            .filter(
            InvoiceModel.payment_method_code.notin_([PaymentMethod.INTERNAL.value, PaymentMethod.DRAWDOWN.value])) \
            .filter((InvoiceModel.disbursement_status_code.is_(None)) |
                    (InvoiceModel.disbursement_status_code == DisbursementStatus.ERRORED.value)) \
            .filter(~InvoiceModel.receipts.any(cast(ReceiptModel.receipt_date, Date) >= disbursement_date.date())) \
            .filter(InvoiceModel.corp_type_code == partner.code) \
            .all()
        current_app.logger.info(invoices)
        return invoices

    @staticmethod
    def get_refund_partial_payment_line_items_for_disbursement(partner) -> List[PaymentLineItemModel]:
        """Return payment line items with partial refunds for disbursement."""
        payment_line_items: List[PaymentLineItemModel] = db.session.query(PaymentLineItemModel) \
            .join(InvoiceModel, PaymentLineItemModel.invoice_id == InvoiceModel.id) \
            .join(RefundsPartialModel, PaymentLineItemModel.id == RefundsPartialModel.payment_line_item_id) \
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value) \
            .filter(InvoiceModel.payment_method_code.in_([PaymentMethod.DIRECT_PAY.value])) \
            .filter((RefundsPartialModel.disbursement_status_code.is_(None)) |
                    (RefundsPartialModel.disbursement_status_code == DisbursementStatus.ERRORED.value)) \
            .filter(InvoiceModel.corp_type_code == partner.code) \
            .all()
        current_app.logger.info(payment_line_items)
        return payment_line_items

    @classmethod
    def get_invoices_for_refund_reversal(cls, partner):
        """Return invoices for refund reversal."""
        # REFUND_REQUESTED for credit card payments, CREDITED for AR and REFUNDED for other payments.
        refund_inv_statuses = (InvoiceStatus.REFUNDED.value, InvoiceStatus.REFUND_REQUESTED.value,
                               InvoiceStatus.CREDITED.value)

        invoices: List[InvoiceModel] = db.session.query(InvoiceModel) \
            .filter(InvoiceModel.invoice_status_code.in_(refund_inv_statuses)) \
            .filter(
            InvoiceModel.payment_method_code.notin_([PaymentMethod.INTERNAL.value, PaymentMethod.DRAWDOWN.value])) \
            .filter(InvoiceModel.disbursement_status_code == DisbursementStatus.COMPLETED.value) \
            .filter(InvoiceModel.corp_type_code == partner.code) \
            .all()
        current_app.logger.info(invoices)
        return invoices

    @classmethod
    def _create_ejv_file_for_partner(cls, batch_type: str):  # pylint:disable=too-many-locals, too-many-statements
        """Create EJV file for the partner and upload."""
        ejv_content: str = ''
        batch_total: float = 0
        control_total: int = 0
        today = datetime.now()
        disbursement_desc = current_app.config.get('CGI_DISBURSEMENT_DESC'). \
            format(today.strftime('%B').upper(), f'{today.day:0>2}')[:100]
        disbursement_desc = f'{disbursement_desc:<100}'

        # Create a ejv file model record.
        ejv_file_model: EjvFileModel = EjvFileModel(
            file_type=EjvFileType.DISBURSEMENT.value,
            file_ref=cls.get_file_name(),
            disbursement_status_code=DisbursementStatus.UPLOADED.value
        ).flush()
        batch_number = cls.get_batch_number(ejv_file_model.id)

        # Get partner list. Each of the partner will go as a JV Header and transactions as JV Details.
        partners = cls._get_partners_by_batch_type(batch_type)
        current_app.logger.info(partners)

        # JV Batch Header
        batch_header: str = cls.get_batch_header(batch_number, batch_type)

        for partner in partners:
            # Find all invoices for the partner to disburse.
            # This includes invoices which are not PAID and invoices which are refunded and partial refunded.
            payment_invoices = cls.get_invoices_for_disbursement(partner)
            refund_reversals = cls.get_invoices_for_refund_reversal(partner)
            invoices = payment_invoices + refund_reversals

            # Process partial refunds for each partner
            refund_partial_items = cls.get_refund_partial_payment_line_items_for_disbursement(partner)

            # If no invoices continue.
            if not invoices and not refund_partial_items:
                continue

            effective_date: str = cls.get_effective_date()
            # Construct journal name
            ejv_header_model: EjvFileModel = EjvHeaderModel(
                partner_code=partner.code,
                disbursement_status_code=DisbursementStatus.UPLOADED.value,
                ejv_file_id=ejv_file_model.id
            ).flush()
            journal_name: str = cls.get_journal_name(ejv_header_model.id)

            # To populate JV Header and JV Details, group these invoices by the distribution
            # and create one JV Header and detail for each.
            distribution_code_set = set()
            invoice_id_list = []
            partial_line_item_id_list = []
            for inv in invoices:
                invoice_id_list.append(inv.id)
                for line_item in inv.payment_line_items:
                    distribution_code_set.add(line_item.fee_distribution_id)

            for line_item in refund_partial_items:
                partial_line_item_id_list.append(line_item.id)
                distribution_code_set.add(line_item.fee_distribution_id)

            for distribution_code_id in list(distribution_code_set):
                distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_id(distribution_code_id)
                credit_distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_id(
                    distribution_code.disbursement_distribution_code_id
                )
                if credit_distribution_code.stop_ejv:
                    continue

                line_items = cls._find_line_items_by_invoice_and_distribution(
                        distribution_code_id, invoice_id_list)

                refund_partial_items = cls._find_refund_partial_items_by_distribution(
                        distribution_code_id, partial_line_item_id_list)

                total: float = 0
                for line in line_items:
                    total += line.total

                partial_refund_total: float = 0
                for refund_partial in refund_partial_items:
                    partial_refund_total += refund_partial.refund_amount

                batch_total += total
                batch_total += partial_refund_total

                debit_distribution = cls.get_distribution_string(distribution_code)  # Debit from BCREG GL
                credit_distribution = cls.get_distribution_string(credit_distribution_code)  # Credit to partner GL

                # JV Header
                ejv_content = '{}{}'.format(ejv_content,  # pylint:disable=consider-using-f-string
                                            cls.get_jv_header(batch_type, cls.get_journal_batch_name(batch_number),
                                                              journal_name, total))
                control_total += 1

                line_number: int = 0
                for line in line_items:
                    # JV Details
                    line_number += 1
                    # Flow Through add it as the invoice id.
                    flow_through = f'{line.invoice_id:<110}'
                    # debit_distribution and credit_distribution stays as is for invoices which are not PAID
                    # For reversals, we just need to reverse the debit and credit.
                    is_reversal = InvoiceModel.find_by_id(line.invoice_id).invoice_status_code in \
                        (InvoiceStatus.REFUNDED.value,
                         InvoiceStatus.REFUND_REQUESTED.value,
                         InvoiceStatus.CREDITED.value)

                    invoice_number = f'#{line.invoice_id}'
                    description = disbursement_desc[:-len(invoice_number)] + invoice_number
                    description = f'{description[:100]:<100}'
                    ejv_content = '{}{}'.format(ejv_content,  # pylint:disable=consider-using-f-string
                                                cls.get_jv_line(batch_type, credit_distribution, description,
                                                                effective_date, flow_through, journal_name, line.total,
                                                                line_number, 'C' if not is_reversal else 'D'))
                    line_number += 1
                    control_total += 1

                    # Add a line here for debit too
                    ejv_content = '{}{}'.format(ejv_content,  # pylint:disable=consider-using-f-string
                                                cls.get_jv_line(batch_type, debit_distribution, description,
                                                                effective_date, flow_through, journal_name, line.total,
                                                                line_number, 'D' if not is_reversal else 'C'))

                    control_total += 1

                partial_refund_number: int = 0
                for refund_partial in refund_partial_items:
                    # JV Details for partial refunds
                    partial_refund_number += 1
                    # Flow Through add it as the refunds_partial id.
                    flow_through = f'{refund_partial.id:<110}'
                    refund_partial_number = f'#{refund_partial.id}'
                    description = disbursement_desc[:-len(refund_partial_number)] + refund_partial_number
                    description = f'{description[:100]:<100}'

                    ejv_content = '{}{}'.format(ejv_content,  # pylint:disable=consider-using-f-string
                                                cls.get_jv_line(batch_type, credit_distribution, description,
                                                                effective_date, flow_through, journal_name,
                                                                refund_partial.refund_amount,
                                                                partial_refund_number, 'D'))
                    partial_refund_number += 1
                    control_total += 1

                    # Add a line here for debit too
                    ejv_content = '{}{}'.format(ejv_content,  # pylint:disable=consider-using-f-string
                                                cls.get_jv_line(batch_type, debit_distribution, description,
                                                                effective_date, flow_through, journal_name,
                                                                refund_partial.refund_amount,
                                                                partial_refund_number, 'C'))
                    control_total += 1

                    # Update partial refund status
                    refund_partial.disbursement_status_code = DisbursementStatus.UPLOADED.value

            # Create ejv invoice/partial_refund link records and set invoice status
            sequence = 1
            sequence = cls._create_ejv_link(invoices, ejv_header_model, sequence, EJVLinkType.INVOICE.value)
            cls._create_ejv_link(refund_partial_items, ejv_header_model, sequence, EJVLinkType.REFUND.value)

        if not ejv_content:
            db.session.rollback()
            return

        # JV Batch Trailer
        jv_batch_trailer: str = cls.get_batch_trailer(batch_number, batch_total, batch_type, control_total)

        ejv_content = f'{batch_header}{ejv_content}{jv_batch_trailer}'
        # Create a file add this content.
        file_path_with_name, trg_file_path = cls.create_inbox_and_trg_files(ejv_content)

        # Upload file and trg to FTP
        cls.upload(ejv_content, cls.get_file_name(), file_path_with_name, trg_file_path)

        # commit changes to DB
        db.session.commit()

        # Add a sleep to prevent collision on file name.
        time.sleep(1)

    @classmethod
    def _find_line_items_by_invoice_and_distribution(cls, distribution_code_id, invoice_id_list) \
            -> List[PaymentLineItemModel]:
        """Find and return all payment line items for this distribution."""
        line_items: List[PaymentLineItemModel] = db.session.query(PaymentLineItemModel) \
            .filter(PaymentLineItemModel.invoice_id.in_(invoice_id_list)) \
            .filter(PaymentLineItemModel.total > 0) \
            .filter(PaymentLineItemModel.fee_distribution_id == distribution_code_id)
        return line_items

    @classmethod
    def _find_refund_partial_items_by_distribution(cls, distribution_code_id, partial_line_item_id_list) \
            -> List[RefundsPartialModel]:
        """Find and return all payment line items for this distribution."""
        line_items: List[RefundsPartialModel] = db.session.query(RefundsPartialModel) \
            .join(PaymentLineItemModel, PaymentLineItemModel.id == RefundsPartialModel.payment_line_item_id) \
            .filter(RefundsPartialModel.payment_line_item_id.in_(partial_line_item_id_list)) \
            .filter(RefundsPartialModel.refund_amount > 0) \
            .filter(PaymentLineItemModel.fee_distribution_id == distribution_code_id) \
            .all()
        return line_items

    @classmethod
    def _get_partners_by_batch_type(cls, batch_type) -> List[CorpTypeModel]:
        """Return partners by batch type."""
        # CREDIT : Ministry GL code -> disbursement_distribution_code_id on distribution_codes table
        # DEBIT : BC Registry GL Code -> distribution_code on fee_schedule, starts with 112
        bc_reg_client_code = current_app.config.get('CGI_BCREG_CLIENT_CODE')  # 112
        query = db.session.query(DistributionCodeModel.distribution_code_id) \
            .filter(DistributionCodeModel.stop_ejv.is_(False) | DistributionCodeModel.stop_ejv.is_(None)) \
            .filter(DistributionCodeModel.account_id.is_(None)) \
            .filter(DistributionCodeModel.disbursement_distribution_code_id.is_(None))

        if batch_type == 'GA':
            # Rule for GA. Credit is 112 and debit is 112.
            partner_distribution_code_ids: List[int] = db.session.scalars(query.filter(
                DistributionCodeModel.client == bc_reg_client_code
            )).all()
        else:
            # Rule for GI. Debit is 112 and credit is not 112.
            partner_distribution_code_ids: List[int] = db.session.scalars(query.filter(
                DistributionCodeModel.client != bc_reg_client_code
            )).all()

        # Find all distribution codes who have these partner distribution codes as disbursement.
        fee_query = db.session.query(DistributionCodeModel.distribution_code_id).filter(
            DistributionCodeModel.disbursement_distribution_code_id.in_(partner_distribution_code_ids))
        fee_distribution_codes: List[int] = db.session.scalars(fee_query).all()

        corp_type_query = db.session.query(FeeScheduleModel.corp_type_code). \
            join(DistributionCodeLinkModel,
                 DistributionCodeLinkModel.fee_schedule_id == FeeScheduleModel.fee_schedule_id).\
            filter(DistributionCodeLinkModel.distribution_code_id.in_(fee_distribution_codes))
        corp_type_codes: List[str] = db.session.scalars(corp_type_query).all()

        return db.session.query(CorpTypeModel).filter(CorpTypeModel.code.in_(corp_type_codes)).all()

    @classmethod
    def _create_ejv_link(cls, items, ejv_header_model, sequence, link_type):
        for item in items:
            link_model = EjvLinkModel(link_id=item.id,
                                      link_type=link_type,
                                      ejv_header_id=ejv_header_model.id,
                                      disbursement_status_code=DisbursementStatus.UPLOADED.value,
                                      sequence=sequence)
            db.session.add(link_model)
            sequence += 1
            item.disbursement_status_code = DisbursementStatus.UPLOADED.value
        db.session.flush()
        return sequence
