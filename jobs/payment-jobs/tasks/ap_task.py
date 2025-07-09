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
"""Task to create AP file for FAS refunds and Disbursement via EFT for non-government orgs without a GL."""

import time
import traceback
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List

from flask import current_app
from more_itertools import batched
from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import EFTRefund as EFTRefundModel
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import EjvLink as EjvLinkModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import Refund as RefundModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import db
from pay_api.services.email_service import JobFailureNotification
from pay_api.utils.enums import (
    APRefundMethod,
    DisbursementStatus,
    EFTShortnameRefundStatus,
    EjvFileType,
    EJVLinkType,
    InvoiceStatus,
    PaymentMethod,
    RoutingSlipStatus,
)
from sqlalchemy import Date, cast

from tasks.common.cgi_ap import CgiAP
from tasks.common.dataclasses import APFlow, APHeader, APLine, APSupplier


def _process_error(row, error_msg: str, error_messages: List[Dict[str, any]], ex: Exception = None):
    """Handle errors in AP file processing."""
    if ex:
        formatted_traceback = "".join(traceback.TracebackException.from_exception(ex).format())
        error_msg = f"{error_msg}\n{formatted_traceback}"
    db.session.rollback()
    current_app.logger.error(f"{{error: {str(ex)}, stack_trace: {traceback.format_exc()}}}")
    error_messages.append({"error": error_msg, "row": row})


class ApTask(CgiAP):
    """Task to create AP (Accounts Payable) Feeder Files.

    Purpose:
    1. Create mailed out cheques for unused amounts on routing slips / eft refunds.
       Delivery instructions are for SBC-Finance only on the frontend. They aren't carted over to the AP batch.
       The AP Address fields are the only fields on the front of the envelope for cheques.
       AP Comment field show up attached to the cheque.

    2. Distribution of funds to non government partners without a GL code (EFT).

    """

    error_messages = []
    has_errors = False

    @classmethod
    def create_ap_files(cls):
        """Create AP files and upload to CGI.

        Steps:
        1. Find all routing slip with status REFUND_AUTHORIZED.
        2. Create AP file and upload to SFTP.
        3. After some time, a feedback file will arrive and Payment-reconciliation queue will move these
           routing slips to REFUNDED. (filter out)
        4. Find all BCA invoices with status PAID. (DRAWDOWN/INTERNAL EXCLUDED)
           These invoices need to be disbursement status ERRORED or None
        5. Find all BCA invoices with status REFUND_REQUESTED or REFUNDED. (DRAWDOWN/INTERNAL EXCLUDED)
           These invoices need to be disbursement status COMPLETED
        6. Create AP file and upload to SFTP.
        7. After some time, a feedback file will arrive and Payment-reconciliation queue will set disbursement
           status to COMPLETED or REVERSED (filter out)
        8. Find all EFT refunds with status APPROVED.
        9. Create AP file and upload to SFTP.
        10. After some time, a feedback file will arrive and Payment-reconciliation queue will move these
            EFT refunds to REFUNDED. (filter out)
        """
        cls.has_errors = False
        cls.error_messages = []

        try:
            cls._create_routing_slip_refund_file()
        except Exception as e:
            _process_error(
                {"task": "create_routing_slip_refund", "ejv_file_type": EjvFileType.REFUND.value},
                "Error creating routing slip refund file",
                cls.error_messages,
                e,
            )
            cls.has_errors = True

        try:
            cls._create_non_gov_disbursement_file()
        except Exception as e:
            _process_error(
                {"task": "create_non_gov_disbursement", "ejv_file_type": EjvFileType.NON_GOV_DISBURSEMENT.value},
                "Error creating non gov disbursement file",
                cls.error_messages,
                e,
            )
            cls.has_errors = True

        try:
            cls._create_eft_refund_file()
        except Exception as e:
            _process_error(
                {"task": "create_eft_refund", "ejv_file_type": EjvFileType.EFT_REFUND.value},
                "Error creating eft refund file",
                cls.error_messages,
                e,
            )
            cls.has_errors = True

        if cls.has_errors and not current_app.config.get("DISABLE_AP_ERROR_EMAIL"):
            notification = JobFailureNotification(
                subject="AP Task Job Failure",
                file_name="ap_task",
                error_messages=cls.error_messages,
                table_name="ejv_file",
                job_name="AP Task Job",
            )
            notification.send_notification()

    @classmethod
    def _create_eft_refund_file(cls):
        """Create AP file for EFT refunds (CHEQUE and EFT) and upload to CGI."""
        eft_refunds_dao = (
            db.session.query(EFTRefundModel)
            .filter(EFTRefundModel.status == EFTShortnameRefundStatus.APPROVED.value)
            .filter(EFTRefundModel.disbursement_status_code.is_(None))
            .filter(EFTRefundModel.refund_amount > 0)
            .all()
        )

        current_app.logger.info(f"Found {len(eft_refunds_dao)} to refund.")

        for refunds in list(batched(eft_refunds_dao, 250)):
            file_name = cls.get_file_name()
            ejv_file_model = EjvFileModel(
                file_type=EjvFileType.EFT_REFUND.value,
                file_ref=file_name,
                disbursement_status_code=DisbursementStatus.UPLOADED.value,
            ).flush()
            current_app.logger.info(f"Creating EJV File Id: {ejv_file_model.id}, File Name: {file_name}")
            batch_number: str = cls.get_batch_number(ejv_file_model.id)
            content: str = cls.get_batch_header(batch_number)
            batch_total = 0
            line_count_total = 0
            for eft_refund in refunds:
                ap_supplier = APSupplier(eft_refund.cas_supplier_number, eft_refund.cas_supplier_site)
                ap_flow = {
                    APRefundMethod.CHEQUE.value: APFlow.EFT_TO_CHEQUE,
                    APRefundMethod.EFT.value: APFlow.EFT_TO_EFT,
                }[eft_refund.refund_method]
                current_app.logger.info(
                    f"Creating refund for EFT Refund {eft_refund.id}, {ap_flow.value} Amount {eft_refund.refund_amount}"
                )
                ap_header = APHeader(
                    ap_flow=ap_flow,
                    total=eft_refund.refund_amount,
                    invoice_number=eft_refund.id,
                    invoice_date=eft_refund.created_on,
                    ap_supplier=ap_supplier,
                )
                ap_line = APLine(
                    ap_flow=ap_flow,
                    total=eft_refund.refund_amount,
                    invoice_number=eft_refund.id,
                    line_number=line_count_total + 1,
                    ap_supplier=ap_supplier,
                )
                content = f"{content}{cls.get_ap_header(ap_header)}{cls.get_ap_invoice_line(ap_line)}"
                line_count_total += 2
                if ap_flow == APFlow.EFT_TO_CHEQUE:
                    content = f"{content}{cls.get_ap_address(ap_flow, eft_refund, eft_refund.id)}"
                    line_count_total += 1
                ap_comment = cls.get_eft_ap_comment(ap_flow, eft_refund, ap_supplier)
                content = f"{content}{ap_comment:<40}"
                line_count_total += 1
                batch_total += eft_refund.refund_amount
                eft_refund.disbursement_status_code = DisbursementStatus.UPLOADED.value

            content = f"{content}{cls.get_batch_trailer(batch_number, batch_total, control_total=line_count_total)}"
            cls._create_file_and_upload(content, file_name)

    @classmethod
    def _create_routing_slip_refund_file(
        cls,
    ):  # pylint:disable=too-many-locals, too-many-statements
        """Create AP file for routing slip refunds (unapplied routing slip amounts) and upload to CGI."""
        routing_slips_dao: List[RoutingSlipModel] = (
            db.session.query(RoutingSlipModel)
            .filter(RoutingSlipModel.status == RoutingSlipStatus.REFUND_AUTHORIZED.value)
            .filter(RoutingSlipModel.refund_amount > 0)
            .all()
        )

        current_app.logger.info(f"Found {len(routing_slips_dao)} to refund.")
        if not routing_slips_dao:
            return

        for routing_slips in list(batched(routing_slips_dao, 250)):
            file_name = cls.get_file_name()
            ejv_file_model: EjvFileModel = EjvFileModel(
                file_type=EjvFileType.REFUND.value,
                file_ref=file_name,
                disbursement_status_code=DisbursementStatus.UPLOADED.value,
            ).flush()

            current_app.logger.info(f"Creating EJV File Id: {ejv_file_model.id}, File Name: {file_name}")
            batch_number: str = cls.get_batch_number(ejv_file_model.id)
            content: str = cls.get_batch_header(batch_number)
            batch_total = 0
            total_line_count: int = 0
            for rs in routing_slips:
                current_app.logger.info(f"Creating refund for {rs.number}, Amount {rs.refund_amount}.")
                refund: RefundModel = RefundModel.find_by_routing_slip_id(rs.id)
                ap_header = APHeader(
                    total=rs.refund_amount,
                    invoice_number=rs.number,
                    invoice_date=datetime.now(tz=timezone.utc),
                    ap_flow=APFlow.ROUTING_SLIP_TO_CHEQUE,
                )
                content = f"{content}{cls.get_ap_header(ap_header)}"
                ap_line = APLine(
                    total=rs.refund_amount,
                    invoice_number=rs.number,
                    line_number=1,
                    ap_flow=APFlow.ROUTING_SLIP_TO_CHEQUE,
                )
                content = f"{content}{cls.get_ap_invoice_line(ap_line)}"
                content = f"{content}{cls.get_ap_address(APFlow.ROUTING_SLIP_TO_CHEQUE, refund.details, rs.number)}"
                total_line_count += 3
                if ap_comment := cls.get_rs_ap_comment(refund.details, rs.number):
                    content = f"{content}{ap_comment:<40}"
                    total_line_count += 1
                batch_total += rs.refund_amount
                rs.status = RoutingSlipStatus.REFUND_UPLOADED.value
            batch_trailer = cls.get_batch_trailer(batch_number, float(batch_total), control_total=total_line_count)
            content = f"{content}{batch_trailer}"
            cls._create_file_and_upload(content, file_name)

    @classmethod
    def get_invoices_for_disbursement(cls, partner):
        """Return invoices for disbursement. Used by EJV and AP."""
        disbursement_date = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(
            days=current_app.config.get("DISBURSEMENT_DELAY_IN_DAYS")
        )
        invoices: List[InvoiceModel] = (
            db.session.query(InvoiceModel)
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value)
            .filter(
                InvoiceModel.payment_method_code.notin_(
                    [
                        PaymentMethod.INTERNAL.value,
                        PaymentMethod.DRAWDOWN.value,
                        PaymentMethod.EFT.value,
                    ]
                )
            )
            .filter(
                (InvoiceModel.disbursement_status_code.is_(None))
                | (InvoiceModel.disbursement_status_code == DisbursementStatus.ERRORED.value)
            )
            .filter(~InvoiceModel.receipts.any(cast(ReceiptModel.receipt_date, Date) >= disbursement_date.date()))
            .filter(InvoiceModel.corp_type_code == partner.code)
            .all()
        )
        current_app.logger.info(invoices)
        return invoices

    @classmethod
    def get_invoices_for_refund_reversal(cls, partner):
        """Return invoices for refund reversal."""
        # REFUND_REQUESTED for credit card payments, CREDITED for AR and REFUNDED for other payments.
        refund_inv_statuses = (
            InvoiceStatus.REFUNDED.value,
            InvoiceStatus.REFUND_REQUESTED.value,
            InvoiceStatus.CREDITED.value,
        )

        invoices: List[InvoiceModel] = (
            db.session.query(InvoiceModel)
            .filter(InvoiceModel.invoice_status_code.in_(refund_inv_statuses))
            .filter(
                InvoiceModel.payment_method_code.notin_(
                    [
                        PaymentMethod.INTERNAL.value,
                        PaymentMethod.DRAWDOWN.value,
                        PaymentMethod.EFT.value,
                    ]
                )
            )
            .filter(InvoiceModel.disbursement_status_code == DisbursementStatus.COMPLETED.value)
            .filter(InvoiceModel.corp_type_code == partner.code)
            .all()
        )
        current_app.logger.info(invoices)
        return invoices

    @classmethod
    def _create_non_gov_disbursement_file(cls):  # pylint:disable=too-many-locals
        """Create AP file for disbursement for non government entities without a GL code via EFT and upload to CGI."""
        ap_flow = APFlow.NON_GOV_TO_EFT
        bca_partner = CorpTypeModel.find_by_code("BCA")
        # TODO these two functions need to be reworked when we onboard BCA again.
        total_invoices: List[InvoiceModel] = cls.get_invoices_for_disbursement(
            bca_partner
        ) + cls.get_invoices_for_refund_reversal(bca_partner)

        current_app.logger.info(f"Found {len(total_invoices)} to disburse.")
        if not total_invoices:
            return

        # 250 MAX is all the transactions the feeder can take per batch.
        for invoices in list(batched(total_invoices, 250)):
            bca_distribution = cls._get_bca_distribution_string()
            file_name = cls.get_file_name()
            ejv_file_model: EjvFileModel = EjvFileModel(
                file_type=EjvFileType.NON_GOV_DISBURSEMENT.value,
                file_ref=file_name,
                disbursement_status_code=DisbursementStatus.UPLOADED.value,
            ).flush()
            current_app.logger.info(f"Creating EJV File Id: {ejv_file_model.id}, File Name: {file_name}")
            # Create a single header record for this file, provides query ejv_file -> ejv_header -> ejv_invoice_links
            # Note the inbox file doesn't include ejv_header when submitting.
            ejv_header_model: EjvFileModel = EjvHeaderModel(
                partner_code="BCA",
                disbursement_status_code=DisbursementStatus.UPLOADED.value,
                ejv_file_id=ejv_file_model.id,
            ).flush()

            batch_number: str = cls.get_batch_number(ejv_file_model.id)
            content: str = cls.get_batch_header(batch_number)
            batch_total = 0
            control_total: int = 0
            for inv in invoices:
                disbursement_invoice_total = inv.total - inv.service_fees
                batch_total += disbursement_invoice_total
                if disbursement_invoice_total == 0:
                    continue
                ap_header = APHeader(
                    total=disbursement_invoice_total,
                    invoice_number=inv.id,
                    invoice_date=inv.created_on,
                    ap_flow=ap_flow,
                )
                content = f"{content}{cls.get_ap_header(ap_header)}"
                control_total += 1
                line_number: int = 0
                for line_item in inv.payment_line_items:
                    if line_item.total == 0:
                        continue
                    ap_line = APLine.from_invoice_and_line_item(inv, line_item, line_number + 1, bca_distribution)
                    ap_line.ap_flow = ap_flow
                    content = f"{content}{cls.get_ap_invoice_line(ap_line)}"
                    line_number += 1
                control_total += line_number
            batch_trailer: str = cls.get_batch_trailer(batch_number, batch_total, control_total=control_total)
            content = f"{content}{batch_trailer}"

            for inv in invoices:
                db.session.add(
                    EjvLinkModel(
                        link_id=inv.id,
                        link_type=EJVLinkType.INVOICE.value,
                        ejv_header_id=ejv_header_model.id,
                        disbursement_status_code=DisbursementStatus.UPLOADED.value,
                    )
                )
                inv.disbursement_status_code = DisbursementStatus.UPLOADED.value
            db.session.flush()

            cls._create_file_and_upload(content, file_name)

    @classmethod
    def _create_file_and_upload(cls, ap_content, file_name):
        """Create file and upload."""
        file_path_with_name, trg_file_path, _ = cls.create_inbox_and_trg_files(ap_content, file_name)
        cls.upload(ap_content, file_name, file_path_with_name, trg_file_path)
        db.session.commit()
        # Sleep to prevent collision on file name.
        time.sleep(1)

    @classmethod
    def _get_bca_distribution_string(cls) -> str:
        valid_date = date.today()
        d = (
            db.session.query(DistributionCodeModel)
            .filter(DistributionCodeModel.name == "BC Assessment")
            .filter(DistributionCodeModel.start_date <= valid_date)
            .filter((DistributionCodeModel.end_date.is_(None)) | (DistributionCodeModel.end_date >= valid_date))
            .one_or_none()
        )
        return f"{d.client}{d.responsibility_centre}{d.service_line}{d.stob}{d.project_code}"
