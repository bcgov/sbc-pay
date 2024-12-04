# Copyright © 2024 Province of British Columbia
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
"""CGI reconciliation file."""
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from flask import current_app
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import EFTRefund as EFTRefundModel
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import EjvLink as EjvLinkModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import PartnerDisbursements as PartnerDisbursementsModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import Refund as RefundModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import db
from pay_api.services import gcp_queue_publisher
from pay_api.services.gcp_queue_publisher import QueueMessage
from pay_api.utils.enums import (
    DisbursementStatus,
    EFTShortnameRefundStatus,
    EjvFileType,
    EJVLinkType,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    PaymentSystem,
    QueueSources,
    RoutingSlipStatus,
)
from sbc_common_components.utils.enums import QueueMessageTypes
from sentry_sdk import capture_message

from pay_queue import config
from pay_queue.minio import get_object

APP_CONFIG = config.get_named_config(os.getenv("DEPLOYMENT_ENV", "production"))


def reconcile_distributions(msg: Dict[str, any], is_feedback: bool = False):
    """Read the file and update distribution details.

    1: Lookup the invoice details based on the file content.
    2: Update the statuses
    """
    if is_feedback:
        _update_feedback(msg)
    else:
        _update_acknowledgement(msg)


def _update_acknowledgement(msg: Dict[str, any]):
    """Log the ack file, we don't know which batch it's for."""
    current_app.logger.info("Ack file received: %s", msg.get("fileName"))


def _update_feedback(msg: Dict[str, any]):  # pylint:disable=too-many-locals, too-many-statements
    # Read the file and find records from the database, and update status.

    file_name: str = msg.get("fileName")
    minio_location: str = msg.get("location")
    file = get_object(minio_location, file_name)
    content = file.data.decode("utf-8-sig")
    group_batches: List[str] = _group_batches(content)

    if _is_processed_or_processing(group_batches["EJV"], file_name):
        return

    has_errors = _process_ejv_feedback(group_batches["EJV"])
    has_errors = _process_ap_feedback(group_batches["AP"]) or has_errors

    if has_errors and not APP_CONFIG.DISABLE_EJV_ERROR_EMAIL:
        _publish_mailer_events(file_name, minio_location)
    current_app.logger.info("Feedback file processing completed.")


def _is_processed_or_processing(group_batches, file_name) -> bool:
    """Check to see if file has already been processed. Mark them as processing."""
    for group_batch in group_batches:
        ejv_file: Optional[EjvFileModel] = None
        for line in group_batch.splitlines():
            is_batch_group: bool = line[2:4] == "BG"
            if is_batch_group:
                batch_number = int(line[15:24])
                ejv_file = EjvFileModel.find_by_id(batch_number)
                if ejv_file.feedback_file_ref:
                    current_app.logger.info(
                        "EJV file id %s with feedback file %s is already processing or has been processed. Skipping.",
                        batch_number,
                        file_name,
                    )
                    return True
                ejv_file.feedback_file_ref = file_name
                ejv_file.save()
    return False


def _process_ejv_feedback(group_batches) -> bool:  # pylint:disable=too-many-locals
    """Process EJV Feedback contents."""
    has_errors = False
    for group_batch in group_batches:
        ejv_file: Optional[EjvFileModel] = None
        receipt_number: Optional[str] = None
        for line in group_batch.splitlines():
            # For all these indexes refer the sharepoint docs refer : https://github.com/bcgov/entity/issues/6226
            is_batch_group = line[2:4] == "BG"
            is_batch_header = line[2:4] == "BH"
            is_jv_header = line[2:4] == "JH"
            is_jv_detail = line[2:4] == "JD"
            if is_batch_group:
                batch_number = int(line[15:24])
                ejv_file = EjvFileModel.find_by_id(batch_number)
            elif is_batch_header:
                return_code = line[7:11]
                return_message = line[11:161]
                ejv_file.disbursement_status_code = _get_disbursement_status(return_code)
                ejv_file.message = return_message.strip()
                if ejv_file.disbursement_status_code == DisbursementStatus.ERRORED.value:
                    has_errors = True
            elif is_jv_header:
                journal_name: str = line[7:17]  # {ministry}{ejv_header_model.id:0>8}
                ejv_header_model_id = int(journal_name[2:])
                ejv_header = EjvHeaderModel.find_by_id(ejv_header_model_id)
                ejv_header_return_code = line[271:275]
                ejv_header.disbursement_status_code = _get_disbursement_status(ejv_header_return_code)
                ejv_header_error_message = line[275:425]
                ejv_header.message = ejv_header_error_message.strip()
                if ejv_header.disbursement_status_code == DisbursementStatus.ERRORED.value:
                    has_errors = True
                # Create a payment record if its a gov account payment.
                elif ejv_file.file_type == EjvFileType.PAYMENT.value:
                    amount = float(line[42:57])
                    receipt_number = line[0:42].strip()
                    _create_payment_record(amount, ejv_header, receipt_number)

            elif is_jv_detail:
                has_errors = _process_jv_details_feedback(ejv_file, has_errors, line, receipt_number)

    db.session.commit()
    return has_errors


@dataclass
class JVDetailsFeedback:
    """JV Details Feedback."""

    ejv_header_model_id: int
    flowthrough: str
    journal_name: str
    invoice_return_code: str
    invoice_return_message: str
    line: str
    receipt_number: str
    invoice: Optional[InvoiceModel] = None
    invoice_link: Optional[EjvLinkModel] = None
    partner_disbursement: Optional[PartnerDisbursementsModel] = None


def _process_jv_details_feedback(ejv_file, has_errors, line, receipt_number) -> bool:
    """Process JV Details Feedback."""
    details = _build_jv_details(line, receipt_number)
    # If the JV process failed, then mark the GL code against the invoice to be stopped
    # for further JV process for the credit GL.
    current_app.logger.info("Is Credit or Debit %s - %s", line[104:105], ejv_file.file_type)
    credit_or_debit_line = details.line[104:105]
    if credit_or_debit_line == "C" and ejv_file.file_type == EjvFileType.DISBURSEMENT.value:
        has_errors = _handle_jv_disbursement_feedback(details, has_errors)
    elif credit_or_debit_line == "D" and ejv_file.file_type == EjvFileType.PAYMENT.value:
        has_errors = _handle_jv_payment_feedback(details, has_errors)
    return has_errors


def _build_jv_details(line, receipt_number) -> JVDetailsFeedback:
    # Work around for CAS, they said fix the feedback files.
    line = _fix_invoice_line(line)
    details = JVDetailsFeedback(
        journal_name=line[7:17],
        ejv_header_model_id=int(line[7:17][2:]),
        line=line,
        flowthrough=line[205:315].strip(),
        invoice_return_code=line[315:319],
        invoice_return_message=line[319:469],
        receipt_number=receipt_number,
    )
    if "-" in details.flowthrough:
        invoice_id = int(details.flowthrough.split("-")[0])
        partner_disbursement_id = int(details.flowthrough.split("-")[1])
        details.partner_disbursement = PartnerDisbursementsModel.find_by_id(partner_disbursement_id)
    else:
        invoice_id = int(details.flowthrough)
    current_app.logger.info("Invoice id - %s", invoice_id)
    details.invoice = InvoiceModel.find_by_id(invoice_id)
    details.invoice_link = (
        db.session.query(EjvLinkModel)
        .filter(EjvLinkModel.ejv_header_id == details.ejv_header_model_id)
        .filter(EjvLinkModel.link_id == invoice_id)
        .filter(EjvLinkModel.link_type == EJVLinkType.INVOICE.value)
        .one_or_none()
    )
    return details


def _handle_jv_disbursement_feedback(details: JVDetailsFeedback, has_errors: bool) -> bool:
    disbursement_status = _get_disbursement_status(details.invoice_return_code)
    details.invoice_link.disbursement_status_code = disbursement_status
    details.invoice_link.message = details.invoice_return_message.strip()
    current_app.logger.info("disbursement_status %s", disbursement_status)
    if disbursement_status == DisbursementStatus.ERRORED.value:
        has_errors = True
        if details.partner_disbursement:
            details.partner_disbursement.status_code = DisbursementStatus.ERRORED.value
            details.partner_disbursement.processed_on = datetime.now(tz=timezone.utc)
        details.invoice.disbursement_status_code = DisbursementStatus.ERRORED.value
        line_items: List[PaymentLineItemModel] = details.invoice.payment_line_items
        for line_item in line_items:
            # Line debit distribution
            debit_distribution: DistributionCodeModel = DistributionCodeModel.find_by_id(line_item.fee_distribution_id)
            credit_distribution: DistributionCodeModel = DistributionCodeModel.find_by_id(
                debit_distribution.disbursement_distribution_code_id
            )
            credit_distribution.stop_ejv = True
    else:
        effective_date = datetime.strptime(details.line[22:30], "%Y%m%d")
        _update_invoice_disbursement_status(details, effective_date)
    return has_errors


def _handle_jv_payment_feedback(details: JVDetailsFeedback, has_errors: bool) -> bool:
    # This is for gov account payment JV.
    details.invoice_link.disbursement_status_code = _get_disbursement_status(details.invoice_return_code)
    details.invoice_link.message = details.invoice_return_message.strip()
    current_app.logger.info("Invoice ID %s", details.invoice.id)
    inv_ref = InvoiceReferenceModel.find_by_invoice_id_and_status(
        details.invoice.id, InvoiceReferenceStatus.ACTIVE.value
    )
    current_app.logger.info(
        "invoice_link.disbursement_status_code %s",
        details.invoice_link.disbursement_status_code,
    )
    if details.invoice_link.disbursement_status_code == DisbursementStatus.ERRORED.value:
        has_errors = True
        # Cancel the invoice reference.
        if inv_ref:
            inv_ref.status_code = InvoiceReferenceStatus.CANCELLED.value
        # Find the distribution code and set the stop_ejv flag to TRUE
        dist_code = DistributionCodeModel.find_by_active_for_account(details.invoice.payment_account_id)
        dist_code.stop_ejv = True
    elif details.invoice_link.disbursement_status_code == DisbursementStatus.COMPLETED.value:
        # Set the invoice status as REFUNDED if it's a JV reversal, else mark as PAID
        effective_date = datetime.strptime(details.line[22:30], "%Y%m%d")
        # No need for credited here as these are just for EJV payments, which are never credited.
        is_reversal = details.invoice.invoice_status_code in (
            InvoiceStatus.REFUNDED.value,
            InvoiceStatus.REFUND_REQUESTED.value,
        )
        _set_invoice_jv_reversal(details.invoice, effective_date, is_reversal)

        # Mark the invoice reference as COMPLETED, create a receipt
        if inv_ref:
            inv_ref.status_code = InvoiceReferenceStatus.COMPLETED.value
        # Find receipt and add total to it, as single invoice can be multiple rows in the file
        if not is_reversal:
            receipt = ReceiptModel.find_by_invoice_id_and_receipt_number(
                invoice_id=details.invoice.id, receipt_number=details.receipt_number
            )
            if receipt:
                receipt.receipt_amount += float(details.line[89:104])
            else:
                ReceiptModel(
                    invoice_id=details.invoice.id,
                    receipt_number=details.receipt_number,
                    receipt_date=datetime.now(tz=timezone.utc),
                    receipt_amount=float(details.line[89:104]),
                ).flush()
    return has_errors


def _set_invoice_jv_reversal(invoice: InvoiceModel, effective_date: datetime, is_reversal: bool):
    # Set the invoice status as REFUNDED if it's a JV reversal, else mark as PAID
    if is_reversal:
        invoice.invoice_status_code = InvoiceStatus.REFUNDED.value
        invoice.refund_date = effective_date
    else:
        invoice.invoice_status_code = InvoiceStatus.PAID.value
        invoice.payment_date = effective_date
        invoice.paid = invoice.total


def _fix_invoice_line(line):
    """Work around for CAS, they said fix the feedback files."""
    # Check for zeros within 300->315 range. Bump them over with spaces.
    if (zero_position := line[300:315].find("0")) > -1:
        spaces_to_insert = 15 - zero_position
        return line[: 300 + zero_position] + (" " * spaces_to_insert) + line[300 + zero_position :]
    return line


def _update_partner_disbursement(partner_disbursement, status_code, effective_date):
    """Update the partner disbursement status."""
    if partner_disbursement is None:
        return
    if status_code == DisbursementStatus.COMPLETED.value and partner_disbursement.is_reversal:
        current_app.logging.error("Marking as completed when it was a reversal.")
    elif status_code == DisbursementStatus.REVERSED.value and not partner_disbursement.is_reversal:
        current_app.logging.error("Marking as reversed when it was not a reversal.")
    partner_disbursement.status_code = status_code
    partner_disbursement.processed_on = datetime.now(tz=timezone.utc)
    partner_disbursement.feedback_on = effective_date


def _update_invoice_disbursement_status(
    details: JVDetailsFeedback,
    effective_date: datetime,
):
    """Update status to reversed if its a refund, else to completed."""
    # This assumes we're only looking at credits.  if credit_or_debit_line == "C"
    if details.line[30:33] == "112":
        _update_partner_disbursement(details.partner_disbursement, DisbursementStatus.REVERSED.value, effective_date)
        details.invoice.disbursement_status_code = DisbursementStatus.REVERSED.value
        details.invoice.disbursement_reversal_date = effective_date
    else:
        _update_partner_disbursement(details.partner_disbursement, DisbursementStatus.COMPLETED.value, effective_date)
        details.invoice.disbursement_status_code = DisbursementStatus.COMPLETED.value
        details.invoice.disbursement_date = effective_date


def _create_payment_record(amount, ejv_header, receipt_number):
    """Create payment record."""
    PaymentModel(
        payment_system_code=PaymentSystem.CGI.value,
        payment_account_id=ejv_header.payment_account_id,
        payment_method_code=PaymentMethod.EJV.value,
        payment_status_code=PaymentStatus.COMPLETED.value,
        receipt_number=receipt_number,
        invoice_amount=amount,
        paid_amount=amount,
        payment_date=datetime.now(),
    ).flush()


def _group_batches(content: str) -> Dict[str, List]:
    """Group batches based on the group and trailer."""
    # A batch starts from BG to BT.
    group_batches: Dict[str, List] = {"EJV": [], "AP": []}
    batch_content: str = ""

    is_ejv = True
    for line in content.splitlines():
        if line[:4] in (
            "GABG",
            "GIBG",
            "APBG",
        ):  # batch starts from GIBG or GABG for JV
            is_ejv = line[:4] in ("GABG", "GIBG")
            batch_content = line
        else:
            batch_content = batch_content + os.linesep + line
            if line[2:4] == "BT":  # batch ends with BT
                if is_ejv:
                    group_batches["EJV"].append(batch_content)
                else:
                    group_batches["AP"].append(batch_content)
    return group_batches


def _get_disbursement_status(return_code: str) -> str:
    """Return disbursement status from return code."""
    if return_code == "0000":
        return DisbursementStatus.COMPLETED.value
    return DisbursementStatus.ERRORED.value


def _publish_mailer_events(file_name: str, minio_location: str):
    """Publish payment message to the mailer queue."""
    payload = {"fileName": file_name, "minioLocation": minio_location}
    try:
        gcp_queue_publisher.publish_to_queue(
            QueueMessage(
                source=QueueSources.PAY_QUEUE.value,
                message_type=QueueMessageTypes.EJV_FAILED.value,
                payload=payload,
                topic=current_app.config.get("ACCOUNT_MAILER_TOPIC"),
            )
        )
    except Exception as e:  # NOQA pylint: disable=broad-except
        current_app.logger.error(e)
        capture_message("EJV Failed message error", level="error")


def _process_ap_feedback(group_batches) -> bool:  # pylint:disable=too-many-locals
    """Process AP Feedback contents."""
    has_errors = False
    for group_batch in group_batches:
        ejv_file: Optional[EjvFileModel] = None
        for line in group_batch.splitlines():
            # For all these indexes refer the sharepoint docs refer : https://github.com/bcgov/entity/issues/6226
            is_batch_group: bool = line[2:4] == "BG"
            is_batch_header: bool = line[2:4] == "BH"
            is_ap_header: bool = line[2:4] == "IH"
            if is_batch_group:
                batch_number = int(line[15:24])
                ejv_file = EjvFileModel.find_by_id(batch_number)
            elif is_batch_header:
                return_code = line[7:11]
                return_message = line[11:161]
                ejv_file.disbursement_status_code = _get_disbursement_status(return_code)
                ejv_file.message = return_message.strip()
                if ejv_file.disbursement_status_code == DisbursementStatus.ERRORED.value:
                    has_errors = True
            elif is_ap_header:
                has_errors = _process_ap_header(line, ejv_file) or has_errors

    db.session.commit()
    return has_errors


def _process_ap_header(line, ejv_file: EjvFileModel) -> bool:
    has_errors = False
    if ejv_file.file_type == EjvFileType.REFUND.value:
        has_errors = _process_ap_header_routing_slips(line)
    elif ejv_file.file_type == EjvFileType.EFT_REFUND.value:
        has_errors = _process_ap_header_eft(line)
    else:
        has_errors = _process_ap_header_non_gov_disbursement(line, ejv_file)
    return has_errors


def _process_ap_header_routing_slips(line) -> bool:
    has_errors = False
    routing_slip_number = line[19:69].strip()
    routing_slip: RoutingSlipModel = RoutingSlipModel.find_by_number(routing_slip_number)
    ap_header_return_code = line[414:418]
    ap_header_error_message = line[418:568]
    if _get_disbursement_status(ap_header_return_code) == DisbursementStatus.ERRORED.value:
        has_errors = True
        routing_slip.status = RoutingSlipStatus.REFUND_REJECTED.value
        capture_message(
            f"Refund failed for {routing_slip_number}, reason : {ap_header_error_message}",
            level="error",
        )
    else:
        routing_slip.status = RoutingSlipStatus.REFUND_PROCESSED.value
        refund = RefundModel.find_by_routing_slip_id(routing_slip.id)
        refund.gl_posted = datetime.now()
        refund.save()
    return has_errors


def _process_ap_header_eft(line) -> bool:
    has_errors = False
    eft_refund_id = line[19:69].strip()
    eft_refund = EFTRefundModel.find_by_id(eft_refund_id)
    ap_header_return_code = line[414:418].strip()
    ap_header_error_message = line[418:568].strip()
    if _get_disbursement_status(ap_header_return_code) == DisbursementStatus.ERRORED.value:
        has_errors = True
        eft_refund.status = EFTShortnameRefundStatus.ERRORED.value
        eft_refund.disbursement_status_code = DisbursementStatus.ERRORED.value
        capture_message(
            f"EFT Refund failed for {eft_refund_id}, reason : {ap_header_error_message}",
            level="error",
        )
    else:
        eft_refund.status = EFTShortnameRefundStatus.COMPLETED.value
        eft_refund.disbursement_status_code = DisbursementStatus.COMPLETED.value
        eft_refund.disbursement_date = datetime.now(tz=timezone.utc)
    eft_refund.save()
    return has_errors


def _process_ap_header_non_gov_disbursement(line, ejv_file: EjvFileModel) -> bool:
    has_errors = False
    invoice_id = line[19:69].strip()
    invoice = InvoiceModel.find_by_id(invoice_id)
    ap_header_return_code = line[414:418]
    ap_header_error_message = line[418:568]
    disbursement_status = _get_disbursement_status(ap_header_return_code)
    invoice_link = (
        db.session.query(EjvLinkModel)
        .join(EjvHeaderModel)
        .join(EjvFileModel)
        .filter(EjvFileModel.id == ejv_file.id)
        .filter(EjvLinkModel.link_id == invoice_id)
        .filter(EjvLinkModel.link_type == EJVLinkType.INVOICE.value)
        .one_or_none()
    )
    invoice_link.disbursement_status_code = disbursement_status
    invoice_link.message = ap_header_error_message.strip()
    if disbursement_status == DisbursementStatus.ERRORED.value:
        invoice.disbursement_status_code = disbursement_status
        has_errors = True
        capture_message(
            f"AP - NON-GOV - Disbursement failed for {invoice_id}, reason : {ap_header_error_message}",
            level="error",
        )
    else:
        # TODO - Fix this on BC Assessment launch, so the effective date reads from the feedback.
        raise NotImplementedError("This is not implemented yet.")
    return has_errors
