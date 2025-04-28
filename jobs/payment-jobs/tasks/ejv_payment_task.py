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
from datetime import datetime, timezone
from typing import List

from flask import current_app
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import EjvLink as EjvLinkModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import RefundsPartial as RefundsPartialModel
from pay_api.models import db
from pay_api.utils.enums import (
    DisbursementStatus,
    EjvFileType,
    EJVLinkType,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
)
from pay_api.utils.util import generate_transaction_number

from tasks.common.cgi_ejv import CgiEjv


class EjvPaymentTask(CgiEjv):
    """Task to create Journal Voucher for gov account payments."""

    @classmethod
    def create_ejv_file(cls):
        """Create JV files and upload to CGI.

        Steps:
        1. Find all accounts for GI or GA.
        2. Find outstanding invoices for payment.
        3. Group by account and create JD for each service fee and filing fee.
        4. Upload the file to minio for future reference.
        5. Upload to sftp for processing. First upload JV file and then a TRG file.
        6. Update the statuses and create records to for the batch.
        """
        cls._create_ejv_file_for_gov_account(batch_type="GI")
        cls._create_ejv_file_for_gov_account(batch_type="GA")

    @classmethod
    def _create_ejv_file_for_gov_account(cls, batch_type: str):  # pylint:disable=too-many-locals, too-many-statements
        """Create EJV file for the partner and upload."""
        ejv_content: str = ""
        batch_total: float = 0
        control_total: int = 0

        ejv_file_model: EjvFileModel = EjvFileModel(
            file_type=EjvFileType.PAYMENT.value,
            file_ref=cls.get_file_name(),
            disbursement_status_code=DisbursementStatus.UPLOADED.value,
        ).flush()
        batch_number = cls.get_batch_number(ejv_file_model.id)

        account_ids = cls._get_account_ids_for_payment(batch_type)

        batch_header: str = cls.get_batch_header(batch_number, batch_type)

        current_app.logger.info("Processing accounts.")
        for account_id in account_ids:
            account_jv: str = ""
            # Find all invoices for the gov account to pay.
            invoices = cls._get_invoices_for_payment(account_id)
            invoices += cls.get_partial_refunds_invoices(account_id)
            pay_account: PaymentAccountModel = PaymentAccountModel.find_by_id(account_id)
            if not invoices or not pay_account.billable:
                continue

            disbursement_desc = f"{pay_account.name[:100]:<100}"
            effective_date: str = cls.get_effective_date()
            ejv_header_model: EjvFileModel = EjvHeaderModel(
                payment_account_id=account_id,
                disbursement_status_code=DisbursementStatus.UPLOADED.value,
                ejv_file_id=ejv_file_model.id,
            ).flush()
            journal_name: str = cls.get_journal_name(ejv_header_model.id)
            debit_distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_active_for_account(
                account_id
            )
            debit_distribution = cls.get_distribution_string(debit_distribution_code)  # Debit from GOV account GL

            line_number: int = 0
            total: float = 0
            current_app.logger.info(f"Processing invoices for account_id: {account_id}.")
            for inv in invoices:
                # If it's a JV reversal credit and debit is reversed.
                is_jv_reversal = inv.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value
                is_partial_refund = (inv.invoice_status_code == InvoiceStatus.PAID.value
                                     and inv.refund_amount and inv.refund_amount > 0)

                # If it's reversal, If there is no COMPLETED invoice reference, then no need to reverse it.
                # Else mark it as CANCELLED, as new invoice reference will be created
                if is_jv_reversal:
                    if (
                        inv_ref := InvoiceReferenceModel.find_by_invoice_id_and_status(
                            inv.id, InvoiceReferenceStatus.COMPLETED.value
                        )
                    ) is None:
                        continue
                    inv_ref.status_code = InvoiceReferenceStatus.CANCELLED.value

                line_items = inv.payment_line_items
                partial_refunds = inv.partial_refunds
                invoice_number = f"#{inv.id}"
                description = disbursement_desc[: -len(invoice_number)] + invoice_number
                description = f"{description[:100]:<100}"

                for line in line_items:
                    # Line can have 2 distribution, 1 for the total and another one for service fees.
                    line_distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_id(
                        line.fee_distribution_id
                    )
                    line_total = line.total

                    if partial_refunds and inv.invoice_status_code == InvoiceStatus.APPROVED.value:
                        # For approved invoice with partial refunds, reduce the line_total by the refund amount
                        # if the line item matches the one in partial refunds
                        for partial_refund in partial_refunds:
                            if partial_refund.line_item_id == line.id:
                                line_total -= partial_refund.refund_amount

                    if is_partial_refund:
                        # Find matching partial refund for this line item
                        matching_refund = next(
                            (pr for pr in partial_refunds if pr.payment_line_item_id == line.id),
                            None
                        )
                        if not matching_refund:
                            continue
                        line_total = matching_refund.refund_amount

                    if line_total > 0:
                        total += line_total
                        line_distribution = cls.get_distribution_string(line_distribution_code)
                        flow_through = f"{line.invoice_id:<110}"
                        # Credit to BCREG GL for a transaction (non-reversal)
                        line_number += 1
                        control_total += 1
                        # If it's normal payment then the Line distribution goes as Credit,
                        # else it goes as Debit as we need to debit the fund from BC registry GL.
                        account_jv = account_jv + cls.get_jv_line(
                            batch_type,
                            line_distribution,
                            description,
                            effective_date,
                            flow_through,
                            journal_name,
                            line_total,
                            line_number,
                            "C" if not is_jv_reversal or not is_partial_refund else "D",
                        )

                        # Debit from GOV ACCOUNT GL for a transaction (non-reversal)
                        line_number += 1
                        control_total += 1
                        # If it's normal payment then the Gov account GL goes as Debit,
                        # else it goes as Credit as we need to credit the fund back to ministry.
                        account_jv = account_jv + cls.get_jv_line(
                            batch_type,
                            debit_distribution,
                            description,
                            effective_date,
                            flow_through,
                            journal_name,
                            line_total,
                            line_number,
                            "D" if not is_jv_reversal or not is_partial_refund else "C",
                        )
                        # If it's partial refund, mark the GL posted as True, so that it's not processed again
                        if is_partial_refund:
                            matching_refund.gl_posted = datetime.now(tz=timezone.utc)
                            # skip the service fee cause we never partially refund service fees
                            continue
                    if line.service_fees > 0:
                        service_fee_distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_id(
                            line_distribution_code.service_fee_distribution_code_id
                        )
                        total += line.service_fees
                        service_fee_distribution = cls.get_distribution_string(service_fee_distribution_code)
                        flow_through = f"{line.invoice_id:<110}"
                        # Credit to BCREG GL for a transaction (non-reversal)
                        line_number += 1
                        control_total += 1
                        account_jv = account_jv + cls.get_jv_line(
                            batch_type,
                            service_fee_distribution,
                            description,
                            effective_date,
                            flow_through,
                            journal_name,
                            line.service_fees,
                            line_number,
                            "C" if not is_jv_reversal else "D",
                        )

                        # Debit from GOV ACCOUNT GL for a transaction (non-reversal)
                        line_number += 1
                        control_total += 1
                        account_jv = account_jv + cls.get_jv_line(
                            batch_type,
                            debit_distribution,
                            description,
                            effective_date,
                            flow_through,
                            journal_name,
                            line.service_fees,
                            line_number,
                            "D" if not is_jv_reversal else "C",
                        )
            batch_total += total

            if total > 0:
                # A JV header for each account.
                control_total += 1
                account_jv = (
                    cls.get_jv_header(
                        batch_type,
                        cls.get_journal_batch_name(batch_number),
                        journal_name,
                        total,
                    )
                    + account_jv
                )
                ejv_content = ejv_content + account_jv

            current_app.logger.info("Creating ejv invoice link records and setting invoice status.")
            sequence = 1
            if is_partial_refund:
                for partial_refund in partial_refunds:
                    current_app.logger.debug(
                        f"Creating EJV partial refund link for partial refund id: {partial_refund.id}"
                    )
                    ejv_partial_refund_link = EjvLinkModel(
                        link_id=partial_refund.id,
                        link_type=EJVLinkType.PARTIAL_REFUND.value,
                        ejv_header_id=ejv_header_model.id,
                        disbursement_status_code=DisbursementStatus.UPLOADED.value,
                        sequence=sequence,
                    )
                    db.session.add(ejv_partial_refund_link)
                    sequence += 1
                    continue
            for inv in invoices:
                current_app.logger.debug(f"Creating EJV Invoice Link for invoice id: {inv.id}")
                ejv_invoice_link = EjvLinkModel(
                    link_id=inv.id,
                    link_type=EJVLinkType.INVOICE.value,
                    ejv_header_id=ejv_header_model.id,
                    disbursement_status_code=DisbursementStatus.UPLOADED.value,
                    sequence=sequence,
                )
                db.session.add(ejv_invoice_link)
                sequence += 1
                current_app.logger.debug(f"Creating Invoice Reference for invoice id: {inv.id}")
                inv_ref = InvoiceReferenceModel(
                    invoice_id=inv.id,
                    invoice_number=generate_transaction_number(inv.id),
                    reference_number=None,
                    status_code=InvoiceReferenceStatus.ACTIVE.value,
                )
                db.session.add(inv_ref)
            db.session.flush()  # Instead of flushing every entity, flush all at once.

        if not ejv_content:
            db.session.rollback()
            return

        batch_trailer: str = cls.get_batch_trailer(batch_number, batch_total, batch_type, control_total)
        ejv_content = f"{batch_header}{ejv_content}{batch_trailer}"
        file_path_with_name, trg_file_path, file_name = cls.create_inbox_and_trg_files(ejv_content)
        current_app.logger.info("Uploading to sftp.")
        cls.upload(ejv_content, file_name, file_path_with_name, trg_file_path)
        db.session.commit()

        # Sleep to prevent collision on file name.
        time.sleep(1)

    @classmethod
    def _get_account_ids_for_payment(cls, batch_type) -> List[int]:
        """Return account IDs for payment."""
        # CREDIT : Distribution code against fee schedule
        # DEBIT : Distribution code against account.
        # Rule for GA. Credit is 112 and debit is 112. For BCREG client code is 112
        # Rule for GI. Credit is 112 and debit is not 112. For BCREG client code is 112
        bc_reg_client_code = current_app.config.get("CGI_BCREG_CLIENT_CODE")
        account_ids = (
            db.session.query(DistributionCodeModel.account_id)
            .filter(DistributionCodeModel.stop_ejv.is_(False) | DistributionCodeModel.stop_ejv.is_(None))
            .filter(DistributionCodeModel.account_id.isnot(None))
            .filter_boolean(batch_type == "GA", DistributionCodeModel.client == bc_reg_client_code)
            .filter_boolean(batch_type != "GA", DistributionCodeModel.client != bc_reg_client_code)
            .all()
        )
        return [account_id_tuple[0] for account_id_tuple in account_ids]

    @classmethod
    def _get_invoices_for_payment(cls, account_id: int) -> List[InvoiceModel]:
        """Return invoices for payments."""
        valid_statuses = (
            InvoiceStatus.APPROVED.value,
            InvoiceStatus.REFUND_REQUESTED.value,
        )
        invoice_ref_subquery = db.session.query(InvoiceReferenceModel.invoice_id).filter(
            InvoiceReferenceModel.status_code.in_((InvoiceReferenceStatus.ACTIVE.value,))
        )

        invoices: List[InvoiceModel] = (
            db.session.query(InvoiceModel)
            .filter(InvoiceModel.invoice_status_code.in_(valid_statuses))
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EJV.value)
            .filter(InvoiceModel.payment_account_id == account_id)
            .filter(InvoiceModel.id.notin_(invoice_ref_subquery))
            .all()
        )
        return invoices

    @classmethod
    def get_partial_refunds_invoices(cls, account_id: int) -> List[InvoiceModel]:
        """Get credit card partial refunds."""
        invoices: List[InvoiceModel] = (
            InvoiceModel.query.join(RefundsPartialModel, RefundsPartialModel.invoice_id == InvoiceModel.id)
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EJV.value)
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value)
            .filter(RefundsPartialModel.gl_posted.is_(None))
            .filter(InvoiceModel.payment_account_id == account_id)
            .order_by(InvoiceModel.id, RefundsPartialModel.id)
            .distinct(InvoiceModel.id)
            .all()
        )

        current_app.logger.info(f"Found {len(invoices)} invoices to process for ejv partial refunds.")
        return invoices
