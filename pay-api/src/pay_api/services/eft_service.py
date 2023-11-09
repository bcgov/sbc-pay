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
"""Service to manage CFS EFT Payments."""
from datetime import datetime

from flask import current_app

from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus, PaymentMethod, PaymentStatus

from .deposit_service import DepositService
from .invoice import Invoice
from .invoice_reference import InvoiceReference
from .payment_account import PaymentAccount
from .payment_line_item import PaymentLineItem


class EftService(DepositService):
    """Service to manage electronic fund transfers."""

    def get_payment_method_code(self):
        """Return EFT as the system code."""
        return PaymentMethod.EFT.value

    def create_invoice(self, payment_account: PaymentAccount, line_items: [PaymentLineItem], invoice: Invoice,
                       **kwargs) -> InvoiceReference:
        """Return a static invoice number for direct pay."""
        # Do nothing here as the invoice references will be created later for eft payment reconciliations (TDI17).

    def apply_credit(self, invoice: Invoice) -> None:
        """Apply eft credit to the invoice."""
        invoice_balance = invoice.total - (invoice.paid or 0)  # balance before applying credits
        payment_account = PaymentAccount.find_by_id(invoice.payment_account_id)
        invoice_model = InvoiceModel.find_by_id(invoice.id)

        payment_account.deduct_eft_credit(invoice_model)
        new_invoice_balance = invoice.total - (invoice.paid or 0)

        payment = self.create_payment(payment_account=payment_account,
                                      invoice=invoice_model,
                                      payment_date=datetime.now(),
                                      paid_amount=invoice_balance - new_invoice_balance).save()

        self.create_invoice_reference(invoice=invoice_model, payment=payment).save()
        self.create_receipt(invoice=invoice_model, payment=payment).save()
        self._release_payment(invoice=invoice)

    def create_payment(self, payment_account: PaymentAccountModel, invoice: InvoiceModel, payment_date: datetime,
                       paid_amount) -> PaymentModel:
        """Create a payment record for an invoice."""
        payment = PaymentModel(payment_method_code=self.get_payment_method_code(),
                               payment_status_code=PaymentStatus.COMPLETED.value,
                               payment_system_code=self.get_payment_system_code(),
                               invoice_number=f'{current_app.config["EFT_INVOICE_PREFIX"]}{invoice.id}',
                               invoice_amount=invoice.total,
                               payment_account_id=payment_account.id,
                               payment_date=payment_date,
                               paid_amount=paid_amount,
                               receipt_number=invoice.id)
        return payment

    @staticmethod
    def create_invoice_reference(invoice: InvoiceModel, payment: PaymentModel) -> InvoiceReferenceModel:
        """Create an invoice reference record."""
        if not(invoice_reference := InvoiceReferenceModel
                .find_any_active_reference_by_invoice_number(payment.invoice_number)):
            invoice_reference = InvoiceReferenceModel()

        invoice_reference.invoice_id = invoice.id
        invoice_reference.invoice_number = payment.invoice_number
        invoice_reference.status_code = InvoiceReferenceStatus.COMPLETED.value \
            if invoice.invoice_status_code == InvoiceStatus.PAID.value \
            else InvoiceReferenceStatus.ACTIVE.value

        return invoice_reference

    @staticmethod
    def create_receipt(invoice: InvoiceModel, payment: PaymentModel) -> ReceiptModel:
        """Create a receipt record for an invoice payment."""
        receipt: ReceiptModel = ReceiptModel(receipt_date=payment.payment_date,
                                             receipt_amount=payment.paid_amount,
                                             invoice_id=invoice.id,
                                             receipt_number=payment.receipt_number)
        return receipt
