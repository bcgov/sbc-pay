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
from dataclasses import dataclass
from typing import List

from flask import current_app
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import EjvLink as EjvLinkModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import RefundsPartial as RefundsPartialModel
from pay_api.models import db
from pay_api.utils.enums import (
    DisbursementStatus,
    EjvFileType,
    EJVLinkType,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    RefundsPartialType,
)
from pay_api.utils.util import generate_transaction_number

from tasks.common.cgi_ejv import CgiEjv


@dataclass
class InvoiceData:
    """Data class for invoice information."""

    is_jv_reversal: bool
    is_partial_refund: bool
    line_items: List[PaymentLineItemModel]
    partial_refunds: List[RefundsPartialModel]


@dataclass
class JVParams:
    """Data class for JV parameters."""

    description: str
    effective_date: str
    journal_name: str
    debit_distribution: str


@dataclass
class LineCounters:
    """Data class for line counters."""

    line_number: int
    control_total: int


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
                partial_refunds = RefundsPartialModel.get_partial_refunds_for_invoice(inv.id)
                invoice_number = f"#{inv.id}"
                description = disbursement_desc[: -len(invoice_number)] + invoice_number
                description = f"{description[:100]:<100}"
                is_partial_refund = cls._is_partial_refund(inv)

                invoice_data = InvoiceData(
                    is_jv_reversal=is_jv_reversal,
                    is_partial_refund=is_partial_refund,
                    line_items=line_items,
                    partial_refunds=partial_refunds
                )

                jv_params = JVParams(
                    description=description,
                    effective_date=effective_date,
                    journal_name=journal_name,
                    debit_distribution=debit_distribution
                )

                line_counters = LineCounters(
                    line_number=line_number,
                    control_total=control_total
                )

                inv_total, line_number, control_total, inv_account_jv = cls._process_invoice_line_items(
                    batch_type,
                    invoice_data,
                    jv_params,
                    line_counters
                )

                total += inv_total
                account_jv += inv_account_jv

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

            for inv in invoices:
                if cls._is_partial_refund(inv):
                    db.session.add_all([
                        EjvLinkModel(
                            link_id=pr.id,
                            link_type=EJVLinkType.PARTIAL_REFUND.value,
                            ejv_header_id=ejv_header_model.id,
                            disbursement_status_code=DisbursementStatus.UPLOADED.value,
                            sequence=seq,
                        )
                        for seq, pr in enumerate(partial_refunds, start=sequence)
                    ])
                    sequence += len(partial_refunds)
                    current_app.logger.debug(f"Created {len(partial_refunds)} EJV partial refund links.")
                else:
                    db.session.add(EjvLinkModel(
                        link_id=inv.id,
                        link_type=EJVLinkType.INVOICE.value,
                        ejv_header_id=ejv_header_model.id,
                        disbursement_status_code=DisbursementStatus.UPLOADED.value,
                        sequence=sequence,
                    ))
                    db.session.add(InvoiceReferenceModel(
                        invoice_id=inv.id,
                        invoice_number=generate_transaction_number(inv.id),
                        reference_number=None,
                        status_code=InvoiceReferenceStatus.ACTIVE.value,
                    ))
                    current_app.logger.debug(f"Created EJV Invoice Link and Invoice Reference for invoice id: {inv.id}")
                    sequence += 1
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

    @classmethod
    def _is_partial_refund(cls, invoice):
        """Check if the invoice is a partial refund."""
        return (invoice.invoice_status_code == InvoiceStatus.PAID.value
                and invoice.refund and invoice.refund > 0)

    @classmethod
    def _process_invoice_line_items(
            cls, batch_type: str, invoice_data: InvoiceData, jv_params: JVParams, line_counters: LineCounters
    ):
        """Process invoice line items and generate JV entries.

        Args:
            batch_type: The type of batch (GA or GI)
            invoice_data: Dict containing invoice information
            (is_jv_reversal, is_partial_refund, line_items, partial_refunds)
            jv_params: Dict containing JV parameters (description, effective_date, journal_name, debit_distribution)
            line_counters: Dict with line_number and control_total

        Returns:
            Tuple containing (total, updated_line_number, updated_control_total, account_jv)
        """
        total = 0
        account_jv = ""
        line_number = line_counters.line_number
        control_total = line_counters.control_total

        for line in invoice_data.line_items:
            # Line can have 2 distribution, 1 for the total and another one for service fees.
            line_distribution_code: DistributionCodeModel = DistributionCodeModel.find_by_id(
                line.fee_distribution_id
            )
            line_total, line_service_fee = cls._calculate_line_fees(line, invoice_data)
            if line_total and line_service_fee is None:
                continue

            if line_total and line_total > 0:
                total += line_total
                # Credit to BCREG GL for a transaction (non-reversal)
                line_number += 1
                control_total += 1
                # If it's normal payment then the Line distribution goes as Credit,
                # else it goes as Debit as we need to debit the fund from BC registry GL.
                account_jv += cls.get_jv_line(
                    batch_type,
                    cls.get_distribution_string(line_distribution_code),
                    jv_params.description,
                    jv_params.effective_date,
                    f"{line.invoice_id:<110}",
                    jv_params.journal_name,
                    line_total,
                    line_number,
                    "C" if not invoice_data.is_jv_reversal or not invoice_data.is_partial_refund else "D",
                )

                # Debit from GOV ACCOUNT GL for a transaction (non-reversal)
                line_number += 1
                control_total += 1
                # If it's normal payment then the Gov account GL goes as Debit,
                # else it goes as Credit as we need to credit the fund back to ministry.
                account_jv += cls.get_jv_line(
                    batch_type,
                    jv_params.debit_distribution,
                    jv_params.description,
                    jv_params.effective_date,
                    f"{line.invoice_id:<110}",
                    jv_params.journal_name,
                    line_total,
                    line_number,
                    "D" if not invoice_data.is_jv_reversal or not invoice_data.is_partial_refund else "C",
                )

            if line_service_fee and line_service_fee > 0:
                service_fee_distribution_code = DistributionCodeModel.find_by_id(
                    line_distribution_code.service_fee_distribution_code_id
                )
                total += line_service_fee

                # Credit to BCREG GL for a transaction (non-reversal)
                line_number += 1
                control_total += 1
                account_jv += cls.get_jv_line(
                    batch_type,
                    cls.get_distribution_string(service_fee_distribution_code),
                    jv_params.description,
                    jv_params.effective_date,
                    f"{line.invoice_id:<110}",
                    jv_params.journal_name,
                    line_service_fee,
                    line_number,
                    "C" if not invoice_data.is_jv_reversal or invoice_data.is_partial_refund else "D",
                )

                # Debit from GOV ACCOUNT GL for a transaction (non-reversal)
                line_number += 1
                control_total += 1
                account_jv += cls.get_jv_line(
                    batch_type,
                    jv_params.debit_distribution,
                    jv_params.description,
                    jv_params.effective_date,
                    f"{line.invoice_id:<110}",
                    jv_params.journal_name,
                    line_service_fee,
                    line_number,
                    "D" if not invoice_data.is_jv_reversal or invoice_data.is_partial_refund else "C",
                )

        return total, line_number, control_total, account_jv

    @classmethod
    def _calculate_line_fees(cls, line: PaymentLineItemModel, invoice_data: InvoiceData) -> tuple[float, float]:
        """Calculate line item fees.

        Based on invoice type (normal invoice or partial refund) calculate line item basic fee and service fee.
        For partial refunds, all refund records for the same line item will be added.
        """
        line_total, line_service_fee = 0, 0

        if invoice_data.is_partial_refund:
            matching_refunds = [pr for pr in invoice_data.partial_refunds if pr.payment_line_item_id == line.id]
            if not matching_refunds:
                return None, None

            for refund in matching_refunds:
                if refund.refund_type == RefundsPartialType.SERVICE_FEES.value:
                    line_service_fee += refund.refund_amount
                else:
                    line_total += refund.refund_amount

            if line_total == 0 and line_service_fee == 0:
                return None, None  # Return None to skip processing this line
        else:
            line_total = line.total
            line_service_fee = line.service_fees

        return line_total, line_service_fee
