# Copyright © 2024 Province of British Columbia
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
"""Query helpers."""
from pay_api.models import db
from pay_api.models.fee_schedule import FeeSchedule
from pay_api.models.invoice import Invoice
from pay_api.models.invoice_reference import InvoiceReference
from pay_api.models.payment_account import PaymentAccount
from pay_api.models.payment_line_item import PaymentLineItem
from sqlalchemy.orm import contains_eager, lazyload, load_only

from pay_api.utils.enums import ViewColumnAliases

class TransactionQuery:
    """Class responsible for generating transaction-related queries."""

    @classmethod
    def generate_base_transaction_query(cls):
        """Generate a base query matching the structure of the Transactions materialized view."""
        return (
            db.session.query(
                Invoice.id.label(ViewColumnAliases.INVOICE_ID.value),
                PaymentLineItem.id.label(ViewColumnAliases.LINE_ITEM_ID.value),
                PaymentAccount.id.label(ViewColumnAliases.ACCOUNT_ID.value),
                InvoiceReference.id.label(ViewColumnAliases.REFERENCE_ID.value),
                Invoice,
                PaymentLineItem,
                PaymentAccount,
                InvoiceReference
            )
            .outerjoin(PaymentAccount, Invoice.payment_account_id == PaymentAccount.id)
            .outerjoin(PaymentLineItem, PaymentLineItem.invoice_id == Invoice.id)
            .outerjoin(
                FeeSchedule,
                FeeSchedule.fee_schedule_id == PaymentLineItem.fee_schedule_id,
            )
            .outerjoin(InvoiceReference, InvoiceReference.invoice_id == Invoice.id)
            .options(
                lazyload("*"),
                load_only(
                    Invoice.corp_type_code,
                    Invoice.created_on,
                    Invoice.payment_date,
                    Invoice.refund_date,
                    Invoice.invoice_status_code,
                    Invoice.total,
                    Invoice.service_fees,
                    Invoice.paid,
                    Invoice.refund,
                    Invoice.folio_number,
                    Invoice.created_name,
                    Invoice.invoice_status_code,
                    Invoice.payment_method_code,
                    Invoice.details,
                    Invoice.business_identifier,
                    Invoice.created_by,
                    Invoice.filing_id,
                    Invoice.bcol_account,
                    Invoice.disbursement_date,
                    Invoice.disbursement_reversal_date,
                    Invoice.overdue_date
                ),
                contains_eager(Invoice.payment_line_items).load_only(
                    PaymentLineItem.description,
                    PaymentLineItem.gst,
                    PaymentLineItem.pst,
                )
                .contains_eager(PaymentLineItem.fee_schedule)
                .load_only(FeeSchedule.filing_type_code),
                contains_eager(Invoice.payment_account).load_only(
                    PaymentAccount.auth_account_id,
                    PaymentAccount.name,
                    PaymentAccount.billable,
                ),
                contains_eager(Invoice.references).load_only(
                    InvoiceReference.invoice_number,
                    InvoiceReference.reference_number,
                    InvoiceReference.status_code,
                )
            )
        )
