# Copyright © 2022 Province of British Columbia
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
"""Task to update refunded invoices that have been processed by BCOL."""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List

from flask import current_app
from pay_api.models import Invoice, InvoiceReference, Payment, db
from pay_api.utils.enums import InvoiceStatus, PaymentSystem
from sentry_sdk import capture_message

from services import oracle_db


class BcolRefundConfirmationTask:  # pylint:disable=too-few-public-methods
    """Task to update refunded invoices that have been processed by BCOL."""

    @classmethod
    def update_bcol_refund_invoices(cls):
        """Update BCOL invoices that are in the REFUND_REQUESTED state to REFUNDED/CREDITED if they have been processed.

        Steps:
        1. get BCOL invoices in pay-db that are in REFUND_REQUESTED state
        2. get BCOL records in colin-db (CPRD) for the invoices from step 1
        3. compare the invoices in pay-db vs bcol records in colin-db
          - update invoices to REFUNDED in pay-db that have the correct refund value in colin-db
          - skip invoices that do not have a refund value in colin-db
          - send a sentry message containing all refunds with mismatch values between pay-db and colin-db
        """
        invoice_refs = cls._get_paydb_invoice_refs_for_update()
        if invoice_refs:
            bcol_refund_records = cls._get_colin_bcol_records_for_invoices(invoice_refs)
            current_app.logger.debug('BCOL refunded invoice numbers: %s', bcol_refund_records)

            if bcol_refund_records:
                cls._compare_and_update_records(invoice_refs, bcol_refund_records)
        else:
            current_app.logger.debug('No BCOL refunds to confirm.')

    @classmethod
    def _get_paydb_invoice_refs_for_update(cls) -> List[InvoiceReference]:
        """Get outstanding refund requested BCOL invoice references."""
        current_app.logger.debug('Collecting refund requested BCOL invoices...')
        return db.session.query(InvoiceReference) \
            .join(Invoice, Invoice.id == InvoiceReference.invoice_id) \
            .join(Payment, Payment.invoice_number == InvoiceReference.invoice_number) \
            .filter(Payment.payment_system_code == PaymentSystem.BCOL.value) \
            .filter(Invoice.invoice_status_code == InvoiceStatus.REFUND_REQUESTED.value).all()

    @classmethod
    def _get_colin_bcol_records_for_invoices(cls, invoice_refs: List[InvoiceReference]) -> Dict[str, Decimal]:
        """Get BCOL refund records for the given invoice references."""
        invoice_numbers_str = ', '.join("'" + str(x.invoice_number) + "'" for x in invoice_refs)
        current_app.logger.debug('Refund requested BCOL invoice references: %s', invoice_numbers_str)

        current_app.logger.debug('Connecting to Oracle instance...')
        cursor = oracle_db.connection.cursor()
        current_app.logger.debug('Collecting COLIN BCOL refund records...')
        # key == invoice_number
        bcol_refunds = cursor.execute(
            f"""
            SELECT key, total_amt
            FROM bconline_billing_record
            WHERE key in ({invoice_numbers_str})
                AND qty = -1
            """
        ).fetchall()

        # set invoice_number as the key (makes it easier map against)
        return {x[0]: Decimal(x[1]) for x in bcol_refunds}

    @classmethod
    def _compare_and_update_records(cls, invoice_refs: List[InvoiceReference], bcol_records: dict):
        """Update the invoices statuses that have been refunded by BCOL."""
        for invoice_ref in invoice_refs:
            if invoice_ref.invoice_number not in bcol_records:
                # no bcol refund record in colin-db yet so move on
                continue

            # refund was processed. Check total is correct.
            invoice = Invoice.find_by_id(invoice_ref.invoice_id)
            if invoice.total + bcol_records[invoice_ref.invoice_number] != 0:
                # send sentry error and skip
                capture_message(f'Invoice refund total mismatch for {invoice_ref.invoice_number}.'
                                f'PAY-DB: {invoice.total} COLIN-DB: {bcol_records[invoice_ref.invoice_number]}',
                                level='error')
                current_app.logger.error('Invoice refund total mismatch for %s', invoice_ref.invoice_number)
                continue

            # refund was processed and value is correct. Update invoice state.
            invoice.invoice_status_code = InvoiceStatus.REFUNDED.value
            db.session.add(invoice)
        db.session.commit()
