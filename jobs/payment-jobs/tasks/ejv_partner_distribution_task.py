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
from datetime import datetime, timedelta, timezone
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
from pay_api.models import PartnerDisbursements as PartnerDisbursementsModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import db
from pay_api.utils.enums import DisbursementStatus, EjvFileType, EJVLinkType, InvoiceStatus, PaymentMethod
from sqlalchemy import Date, cast

from tasks.common.cgi_ejv import CgiEjv
from tasks.common.dataclasses import Disbursement, DisbursementLineItem


class EjvPartnerDistributionTask(CgiEjv):
    """Task to create EJV Files."""

    @classmethod
    def create_ejv_file(cls):
        """Create JV files and upload to CGI.

        Steps:
        1. Find all invoices/partial refunds/EFT reversals for disbursements.
        2. Group by fee schedule and create JV Header and JV Details.
        3. Upload the file to minio for future reference.
        4. Upload to sftp for processing. First upload JV file and then a TRG file.
        5. Update the statuses and create records to for the batch.
        """
        cls._create_ejv_file_for_partner(batch_type='GI')  # Internal ministry
        cls._create_ejv_file_for_partner(batch_type='GA')  # External ministry

    @staticmethod
    def get_disbursement_by_distribution_for_partner(partner) -> List[Disbursement]:
        """Return invoices for disbursement. Used by EJV and AP."""
        # Internal invoices aren't disbursed to partners, DRAWDOWN is handled by the mainframe.
        # EFT is handled by the PartnerDisbursements table.
        # ##################################################### Original (Legacy way) - invoice.disbursement_status_code
        # Eventually we'll abanadon this and use the PartnerDisbursements table for all disbursements.
        # We'd need a migration and more changes to move it to the table.
        skip_payment_methods = [PaymentMethod.INTERNAL.value, PaymentMethod.DRAWDOWN.value, PaymentMethod.EFT.value]
        disbursement_date = datetime.today() - timedelta(days=current_app.config.get('DISBURSEMENT_DELAY_IN_DAYS'))
        base_query = db.session.query(InvoiceModel, PaymentLineItemModel, DistributionCodeModel) \
            .join(PaymentLineItemModel, PaymentLineItemModel.invoice_id == InvoiceModel.id) \
            .join(DistributionCodeModel,
                  DistributionCodeModel.distribution_code_id == PaymentLineItemModel.fee_distribution_id) \
            .filter(InvoiceModel.payment_method_code.notin_(skip_payment_methods)) \
            .filter(InvoiceModel.corp_type_code == partner.code) \
            .filter(PaymentLineItemModel.total > 0) \
            .filter(DistributionCodeModel.stop_ejv.is_(False) | DistributionCodeModel.stop_ejv.is_(None)) \
            .order_by(DistributionCodeModel.distribution_code_id, PaymentLineItemModel.id)

        transactions = base_query.filter((InvoiceModel.disbursement_status_code.is_(None)) |
                                         (InvoiceModel.disbursement_status_code == DisbursementStatus.ERRORED.value)) \
            .filter(~InvoiceModel.receipts.any(cast(ReceiptModel.receipt_date, Date) >= disbursement_date.date())) \
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value) \
            .all()

        # REFUND_REQUESTED for credit card payments, CREDITED for AR and REFUNDED for other payments.
        reversals = base_query.filter(InvoiceModel.invoice_status_code.in_([InvoiceStatus.REFUNDED.value,
                                                                            InvoiceStatus.REFUND_REQUESTED.value,
                                                                            InvoiceStatus.CREDITED.value])) \
            .filter(InvoiceModel.disbursement_status_code == DisbursementStatus.COMPLETED.value) \
            .all()

        disbursement_rows = []
        for invoice, payment_line_item, distribution_code in transactions + reversals:
            disbursement_rows.append(Disbursement(
                bcreg_distribution_code=distribution_code,
                partner_distribution_code=distribution_code.partner_distribution_code,
                line_item=DisbursementLineItem(
                    amount=payment_line_item.total,
                    flow_through=f'{invoice.id:<110}',
                    description_identifier=f'#{invoice.id}',
                    is_reversal=invoice.invoice_status_code in [InvoiceStatus.REFUNDED.value,
                                                                InvoiceStatus.REFUND_REQUESTED.value,
                                                                InvoiceStatus.CREDITED.value],
                    disbursement_type=EJVLinkType.INVOICE.value,
                    identifier=invoice.id,
                    is_legacy=True
                )
            ))
        # ################################################################# END OF Legacy way of handling disbursements.

        # Partner disbursements - New
        partner_disbursements = db.session.query(PartnerDisbursementsModel,
                                                 PaymentLineItemModel,
                                                 DistributionCodeModel) \
            .join(PaymentLineItemModel, PaymentLineItemModel.invoice_id == PartnerDisbursementsModel.target_id,
                  PartnerDisbursementsModel.target_type == EJVLinkType.INVOICE.value) \
            .join(DistributionCodeModel,
                  DistributionCodeModel.distribution_code_id == PaymentLineItemModel.fee_distribution_id) \
            .filter(PartnerDisbursementsModel.status_code.is_(None)) \
            .filter(PartnerDisbursementsModel.corp_type_code == partner.code) \
            .filter(DistributionCodeModel.stop_ejv.is_(False) | DistributionCodeModel.stop_ejv.is_(None)) \
            .order_by(DistributionCodeModel.distribution_code_id, PaymentLineItemModel.id) \
            .all()

        for partner_disbursement, distribution_code in partner_disbursements:
            suffix = 'PR' if partner_disbursement.disbursement_type == EJVLinkType.PARTIAL_REFUND else 'PD'
            disbursement_rows.append(Disbursement(
                bcreg_distribution_code=distribution_code,
                partner_distribution_code=distribution_code.partner_distribution_code,
                line_item=DisbursementLineItem(
                    amount=partner_disbursement.amount,
                    flow_through=f'{suffix}{partner_disbursement.target_id:<110}',
                    description_identifier=f'{suffix}#{partner_disbursement.id}',
                    is_reversal=partner_disbursement.is_reversal,
                    disbursement_type=partner_disbursement.disbursement_type,
                    identifier=partner_disbursement.target_id,
                    is_legacy=False
                )
            ))
        disbursement_rows.sort(key=lambda x: x.bcreg_distribution_code.id)
        return disbursement_rows

    @classmethod
    def _create_ejv_file_for_partner(cls, batch_type: str):  # pylint:disable=too-many-locals, too-many-statements
        """Create EJV file for the partner and upload."""
        ejv_content, batch_total, control_total = '', 0.0, 0
        today = datetime.now(tz=timezone.utc)
        disbursement_desc = current_app.config.get('CGI_DISBURSEMENT_DESC'). \
            format(today.strftime('%B').upper(), f'{today.day:0>2}')[:100]
        disbursement_desc = f'{disbursement_desc:<100}'
        ejv_file_model = EjvFileModel(
            file_type=EjvFileType.DISBURSEMENT.value,
            file_ref=cls.get_file_name(),
            disbursement_status_code=DisbursementStatus.UPLOADED.value
        ).flush()
        batch_number = cls.get_batch_number(ejv_file_model.id)
        batch_header = cls.get_batch_header(batch_number, batch_type)
        effective_date = cls.get_effective_date()
        # Each of the partner will go as a JV Header and transactions as JV Details.
        for partner in cls._get_partners_by_batch_type(batch_type):
            current_app.logger.info(partner)
            if not (disbursements := cls.get_disbursement_by_distribution_for_partner(partner)):
                continue

            ejv_header_model = EjvHeaderModel(
                partner_code=partner.code,
                disbursement_status_code=DisbursementStatus.UPLOADED.value,
                ejv_file_id=ejv_file_model.id
            ).flush()
            journal_name = cls.get_journal_name(ejv_header_model.id)
            sequence = 1
            for disbursement in disbursements:
                # debit_distribution and credit_distribution stays as is for invoices which are not PAID
                ejv_content = '{}{}'.format(ejv_content,  # pylint:disable=consider-using-f-string
                                            cls.get_jv_header(batch_type, cls.get_journal_batch_name(batch_number),
                                                              journal_name, disbursement.total))
                control_total += 1
                line_number = 1
                batch_total += disbursement.line_item.amount
                dl = disbursement.line_item
                description = disbursement_desc[:-len(dl.description_identifier)] + dl.description_identifier
                description = f'{description[:100]:<100}'
                for credit_debit_row in range(1, 2):
                    target_distribution = cls.get_distribution_string(
                        dl.partner_distribution_code if credit_debit_row == 1 else dl.bcreg_distribution_code
                    )
                    # For payment flow, credit the GL partner code, debit the BCREG GL code.
                    # Reversal is the opposite debit the GL partner code, credit the BCREG GL Code.
                    credit_debit = 'D' if dl.is_reversal and credit_debit_row == 1 else \
                        'C' if credit_debit_row == 1 else 'D'
                    jv_line = cls.get_jv_line(batch_type,
                                              target_distribution,
                                              description,
                                              effective_date,
                                              dl.flow_through,
                                              journal_name,
                                              dl.amount,
                                              line_number,
                                              credit_debit)
                    ejv_content = '{}{}'.format(ejv_content, jv_line)  # pylint:disable=consider-using-f-string
                    line_number += 1
                    control_total += 1

                cls._update_disbursement_status_and_ejv_link(dl, ejv_header_model, sequence)
                sequence += 1

            db.session.flush()

        if not ejv_content:
            db.session.rollback()
            return

        jv_batch_trailer = cls.get_batch_trailer(batch_number, batch_total, batch_type, control_total)
        ejv_content = f'{batch_header}{ejv_content}{jv_batch_trailer}'
        file_path_with_name, trg_file_path, file_name = cls.create_inbox_and_trg_files(ejv_content)
        cls.upload(ejv_content, file_name, file_path_with_name, trg_file_path)

        db.session.commit()

        # To prevent collision on file name.
        time.sleep(1)

    @classmethod
    def _update_disbursement_status_and_ejv_link(cls,
                                                 target: Disbursement,
                                                 ejv_header_model: EjvHeaderModel,
                                                 sequence: int):
        """Update disbursement status and create EJV Link."""
        if target.is_legacy:
            invoice = InvoiceModel.find_by_id(target.identifier)
            invoice.disbursement_status_code = DisbursementStatus.UPLOADED.value
        else:
            # Only EFT is using partner disbursements table for now, eventually we want to move our disbursement
            # process over to something similar: Where we have an entire table setup that
            # is used to track disbursements, instead of just the three column approach that
            # doesn't work when there are multiple reversals etc.
            partner_disbursement = PartnerDisbursementsModel.find_by_id(target.identifier)
            partner_disbursement.status_code = DisbursementStatus.UPLOADED.value
            partner_disbursement.processed_on = datetime.now(tz=timezone.utc)

        db.session.add(EjvLinkModel(link_id=target.identifier,
                                    link_type=target.disbursement_type,
                                    ejv_header_id=ejv_header_model.id,
                                    disbursement_status_code=DisbursementStatus.UPLOADED.value,
                                    sequence=sequence))

    @classmethod
    def _get_partners_by_batch_type(cls, batch_type) -> List[CorpTypeModel]:
        """Return partners by batch type."""
        # CREDIT : Ministry GL code -> disbursement_distribution_code_id on distribution_codes table
        # DEBIT : BC Registry GL Code -> distribution_code on fee_schedule, starts with 112
        bc_reg_client_code = current_app.config.get('CGI_BCREG_CLIENT_CODE')  # 112
        # Rule for GA. Credit is 112 and debit is 112.
        # Rule for GI. Debit is 112 and credit is not 112.
        query = db.session.query(DistributionCodeModel.distribution_code_id) \
            .filter(DistributionCodeModel.stop_ejv.is_(False) | DistributionCodeModel.stop_ejv.is_(None)) \
            .filter(DistributionCodeModel.account_id.is_(None)) \
            .filter(DistributionCodeModel.disbursement_distribution_code_id.is_(None)) \
            .filter_conditionally(True if batch_type == 'GA' else None,
                                  DistributionCodeModel.client == bc_reg_client_code) \
            .filter_conditionally(True if batch_type == 'GI' else None,
                                  DistributionCodeModel.client != bc_reg_client_code)

        # Find all distribution codes who have these partner distribution codes as disbursement.
        partner_distribution_codes = db.session.query(DistributionCodeModel.distribution_code_id).filter(
            DistributionCodeModel.disbursement_distribution_code_id.in_(query))

        corp_type_query = db.session.query(FeeScheduleModel.corp_type_code) \
            .join(DistributionCodeLinkModel,
                  DistributionCodeLinkModel.fee_schedule_id == FeeScheduleModel.fee_schedule_id) \
            .filter(DistributionCodeLinkModel.distribution_code_id.in_(partner_distribution_codes))

        result = db.session.query(CorpTypeModel) \
            .filter(CorpTypeModel.has_partner_disbursements.is_(True)) \
            .filter(CorpTypeModel.code.in_(corp_type_query)).all()
        return result
