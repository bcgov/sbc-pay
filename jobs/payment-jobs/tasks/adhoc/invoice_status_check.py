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
"""Adhoc task to check invoice status against PayBC order status."""

from decimal import Decimal

from flask import current_app
from requests import HTTPError
from sqlalchemy.orm import lazyload

from pay_api.models import Invoice as InvoiceModel
from pay_api.services.direct_pay_service import DirectPayService
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import (
    AuthHeaderType,
    ContentType,
    InvoiceReferenceStatus,
    InvoiceStatus,
    PaymentMethod,
)
from utils.logger import LoggerUtil

STATUS_PAID = ("PAID", "CMPLT")
STATUS_CREATED = ("PNDNG", "INPRG")
STATUS_REFUNDED = "CMPLT"


class AdhocInvoiceStatusCheckTask:
    """Adhoc task to check invoice status consistency with PayBC."""

    @classmethod
    def _get_logger(cls):
        """Get console logger without StructuredLogHandler."""
        return LoggerUtil.get_console_logger("AdhocInvoiceStatusCheckTask")

    @classmethod
    def _get_invoice_reference(cls, invoice):
        """Get COMPLETED or ACTIVE invoice reference."""
        for status in [
            InvoiceReferenceStatus.COMPLETED.value,
            InvoiceReferenceStatus.ACTIVE.value,
        ]:
            ref = next(
                (r for r in invoice.references if r.status_code == status),
                None,
            )
            if ref:
                return ref
        raise ValueError(f"Invoice {invoice.id} has no COMPLETED or ACTIVE references")

    @classmethod
    def _query_order_status(cls, invoice):
        """Request order status from PayBC."""
        token = DirectPayService().get_token().json()
        access_token = token.get("access_token")
        ref = cls._get_invoice_reference(invoice)
        config = current_app.config
        base_url = config.get("PAYBC_DIRECT_PAY_BASE_URL")
        ref_number = config.get("PAYBC_DIRECT_PAY_REF_NUMBER")
        payment_url = f"{base_url}/paybc/payment/{ref_number}/{ref.invoice_number}"
        pay_connector = config.get("PAY_CONNECTOR_AUTH")
        return OAuthService.get(
            payment_url,
            access_token,
            AuthHeaderType.BEARER,
            ContentType.JSON,
            additional_headers={"Pay-Connector": pay_connector},
        ).json()

    @classmethod
    def _get_expected_paybc_statuses(cls, invoice_status):
        """Get expected PayBC statuses for a given invoice status."""
        status_map = {
            InvoiceStatus.PAID.value: STATUS_PAID,
            InvoiceStatus.CREATED.value: STATUS_CREATED,
            InvoiceStatus.REFUNDED.value: STATUS_REFUNDED,
        }
        return status_map.get(invoice_status)

    @classmethod
    def _extract_posted_refund_amount(cls, status_response):
        """Extract posted refund amount from PayBC response."""
        if amount := status_response.get("postedrefundamount"):
            return Decimal(str(amount))

        total = sum(
            Decimal(str(refund.get("postedrefundamount", 0)))
            for line in status_response.get("revenue", [])
            for refund in line.get("refund_data", [])
            if refund.get("postedrefundamount")
        )
        return total if total > 0 else None

    @classmethod
    def _to_decimal(cls, value):
        """Convert value to Decimal."""
        return Decimal(str(value or 0))

    @classmethod
    def _check_refund_amount_mismatch(cls, invoice, posted_refund_amount):
        """Check if invoice refund matches PayBC posted refund."""  # noqa: E501
        if not posted_refund_amount:
            return False

        db_refund = cls._to_decimal(invoice.refund)
        paybc_refund = cls._to_decimal(posted_refund_amount)
        if db_refund != paybc_refund:
            cls._get_logger().warning(
                f"Invoice {invoice.id} refund amount mismatch - DB refund: {db_refund}, PayBC posted: {paybc_refund}"
            )
            return True
        return False

    @classmethod
    def _check_trnamount_mismatch(cls, invoice, invoice_status, paybc_trnamount):
        """Check if trnamount matches invoice total or paid."""  # noqa: E501
        if not paybc_trnamount:
            return False

        is_created = invoice_status == InvoiceStatus.CREATED.value
        db_amount = cls._to_decimal(invoice.total if is_created else invoice.paid)
        paybc_amount = cls._to_decimal(paybc_trnamount)

        if db_amount != paybc_amount:
            amount_type = "total" if is_created else "paid"
            cls._get_logger().warning(
                f"Invoice {invoice.id} {amount_type} mismatch - "
                f"SBC-PAY-DB {amount_type}: {db_amount}, "
                f"PayBC trnamount: {paybc_amount}"  # noqa: E501
            )
            return True
        return False

    @classmethod
    def _check_pndng_status(cls, invoice, invoice_status, paybc_status):
        """Check PNDNG status: paid should be $0 and status CREATED."""  # noqa: E501
        if paybc_status != "PNDNG":
            return False

        paid_amount = cls._to_decimal(invoice.paid)
        if paid_amount != Decimal("0"):
            cls._get_logger().warning(f"Invoice {invoice.id} PNDNG status - paid should be $0 but is {paid_amount}")
            return True

        if invoice_status != InvoiceStatus.CREATED.value:
            cls._get_logger().warning(
                f"Invoice {invoice.id} PNDNG status - status should be CREATED but is {invoice_status}"
            )
            return True
        return False

    @classmethod
    def _check_status_mismatch(cls, invoice, invoice_status, paybc_status):
        """Check if invoice status matches PayBC status and log mismatch."""
        expected_statuses = cls._get_expected_paybc_statuses(invoice_status)
        if not expected_statuses:
            cls._get_logger().error(
                f"Invoice {invoice.id} unknown status - DB: {invoice_status}, PayBC: {paybc_status}"
            )
            return False

        if paybc_status not in expected_statuses:
            cls._get_logger().warning(
                f"Invoice {invoice.id} status mismatch - DB: {invoice_status}, PayBC: {paybc_status}"
            )
            return True

        return False

    @classmethod
    def _log_invoice_details(
        cls,
        idx,
        total_count,
        invoice,
        invoice_status,
        paybc_status,
        posted_refund,
        paybc_trnamount,
    ):
        """Log invoice details with formatted padding."""
        db_refund = cls._to_decimal(invoice.refund)
        db_paid = cls._to_decimal(invoice.paid)
        db_total = cls._to_decimal(invoice.total)

        # Format values with padding for alignment
        status_db = invoice_status.ljust(8)
        status_paybc = (paybc_status or "None").ljust(6)
        refund_db = str(db_refund).rjust(8)
        refund_paybc = str(posted_refund or "None").rjust(8)
        paid_db = str(db_paid).rjust(8)
        paid_paybc = str(paybc_trnamount or "None").rjust(8)
        total_db = str(db_total).rjust(8)

        # Calculate padding width based on total_count digits
        padding_width = len(str(total_count))
        padding_format = f"[{idx:{padding_width}d}/{total_count}]"
        cls._get_logger().info(
            f"{padding_format} Invoice {invoice.id} | "
            f"Status: DB={status_db} PayBC={status_paybc} | "
            f"Refund: DB={refund_db} PayBC={refund_paybc} | "
            f"Paid: DB={paid_db} PayBC={paid_paybc} | "
            f"Total: DB={total_db}"
        )

    @classmethod
    def _print_summary(cls, total_invoices, mismatch_count, problem_invoices):
        """Print summary of status check results."""
        match_count = total_invoices - mismatch_count
        cls._get_logger().info(
            f"Completed invoice status check for Direct Pay invoices. "
            f"Total invoices checked: {total_invoices}, "
            f"matched: {match_count}, "
            f"mismatches found: {mismatch_count}."
        )
        if problem_invoices:
            invoice_list = ", ".join(map(str, sorted(problem_invoices)))
            cls._get_logger().info(f"Invoices with issues: {invoice_list}")

    @classmethod
    def check_invoice_statuses(cls):
        """Check invoice statuses against PayBC order status for Direct Pay."""  # noqa: E501
        # Get total count first (faster than loading all records)
        total_count = (
            InvoiceModel.query.filter(InvoiceModel.payment_method_code == PaymentMethod.DIRECT_PAY.value)
            .filter(InvoiceModel.invoice_status_code != InvoiceStatus.REFUND_REQUESTED.value)
            .count()
        )

        cls._get_logger().info(f"Found {total_count} Direct Pay invoices to check. Hitting PAYBC API for each invoice.")

        # Use yield_per to stream results instead of loading all into memory
        # Disable eager loading to avoid uniquing/row buffering issues
        invoice_query = (
            InvoiceModel.query.options(lazyload("*"))
            .filter(InvoiceModel.payment_method_code == PaymentMethod.DIRECT_PAY.value)
            .filter(InvoiceModel.invoice_status_code != InvoiceStatus.REFUND_REQUESTED.value)
            .order_by(InvoiceModel.id)
            .yield_per(1000)
        )

        mismatch_count = 0
        problem_invoices = set()

        for idx, invoice in enumerate(invoice_query, 1):
            try:
                status_response = cls._query_order_status(invoice)
                invoice_status = invoice.invoice_status_code
                paybc_status = status_response.get("paymentstatus")
                posted_refund = cls._extract_posted_refund_amount(status_response)
                paybc_trnamount = status_response.get("trnamount")

                cls._log_invoice_details(
                    idx,
                    total_count,
                    invoice,
                    invoice_status,
                    paybc_status,
                    posted_refund,
                    paybc_trnamount,
                )

                checks = [
                    cls._check_pndng_status(invoice, invoice_status, paybc_status),
                    cls._check_status_mismatch(invoice, invoice_status, paybc_status),
                    cls._check_refund_amount_mismatch(invoice, posted_refund),
                ]
                if invoice_status != InvoiceStatus.CREATED.value:
                    checks.append(cls._check_trnamount_mismatch(invoice, invoice_status, paybc_trnamount))

                if sum(checks) > 0:
                    mismatch_count += sum(checks)
                    problem_invoices.add(invoice.id)
            except ValueError as ve:
                # Skip invoices without COMPLETED or ACTIVE references
                if "no COMPLETED or ACTIVE references" in str(ve):
                    cls._get_logger().info(f"Invoice {invoice.id} - no COMPLETED or ACTIVE references, skipping")
                    continue
                # Re-raise other ValueErrors
                raise
            except HTTPError as http_err:
                # For CREATED invoices, 404 is expected (not yet in PayBC)
                is_404 = http_err.response is not None and http_err.response.status_code == 404
                if is_404 and invoice.invoice_status_code == InvoiceStatus.CREATED.value:
                    cls._get_logger().info(
                        f"Invoice {invoice.id} CREATED status - 404 from PayBC (expected, not yet created)"
                    )
                else:
                    cls._get_logger().error(
                        f"Invoice {invoice.id} HTTPError: {str(http_err)}",
                        exc_info=True,
                    )
                    mismatch_count += 1
                    problem_invoices.add(invoice.id)
            except Exception as e:  # noqa: BLE001
                cls._get_logger().error(f"Invoice {invoice.id} Error: {str(e)}", exc_info=True)
                mismatch_count += 1
                problem_invoices.add(invoice.id)

        cls._print_summary(total_count, mismatch_count, problem_invoices)
