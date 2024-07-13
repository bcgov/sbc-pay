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
"""Service to manage CFS EFT Payments."""
import os
from datetime import datetime
from typing import Any, Dict, List

from flask import current_app
from jinja2 import Environment, FileSystemLoader

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import EFTRefund as EFTRefundModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models.eft_refund_email_list import EFTRefundEmailList
from pay_api.services.email_service import send_email
from pay_api.utils.enums import (
    CfsAccountStatus, EFTCreditInvoiceStatus, InvoiceReferenceStatus, PaymentMethod, PaymentStatus, PaymentSystem)
from pay_api.utils.user_context import user_context
from pay_api.utils.util import get_str_by_path

from .deposit_service import DepositService
from .invoice import Invoice
from .invoice_reference import InvoiceReference
from .payment_account import PaymentAccount
from .payment_line_item import PaymentLineItem


class EftService(DepositService):
    """Service to manage electronic fund transfers."""

    def get_payment_method_code(self):
        """Return EFT as the payment method code."""
        return PaymentMethod.EFT.value

    def get_payment_system_code(self):
        """Return PAYBC as the system code."""
        return PaymentSystem.PAYBC.value

    def create_account(self, identifier: str, contact_info: Dict[str, Any], payment_info: Dict[str, Any],
                       **kwargs) -> CfsAccountModel:
        """Create an account for the EFT transactions."""
        # Create CFS Account model instance, set the status as PENDING
        current_app.logger.info(f'Creating EFT account details in PENDING status for {identifier}')
        cfs_account = CfsAccountModel()
        cfs_account.status = CfsAccountStatus.PENDING.value
        cfs_account.payment_method = PaymentMethod.EFT.value
        return cfs_account

    def create_invoice(self, payment_account: PaymentAccount, line_items: List[PaymentLineItem], invoice: Invoice,
                       **kwargs) -> None:
        """Do nothing here, we create invoice references on the create CFS_INVOICES job."""
        self.ensure_no_payment_blockers(payment_account)

    def apply_credit(self,
                     invoice: Invoice,
                     payment_date: datetime = datetime.now(),
                     auto_save: bool = True) -> tuple:
        """Apply eft credit to the invoice."""
        invoice_balance = invoice.total - (invoice.paid or 0)  # balance before applying credits
        payment_account = PaymentAccount.find_by_id(invoice.payment_account_id)
        invoice_model = InvoiceModel.find_by_id(invoice.id)

        payment_account.deduct_eft_credit(invoice_model)
        new_invoice_balance = invoice.total - (invoice.paid or 0)

        payment = self.create_payment(payment_account=payment_account,
                                      invoice=invoice_model,
                                      payment_date=payment_date,
                                      paid_amount=invoice_balance - new_invoice_balance)

        receipt = self.create_receipt(invoice=invoice_model, payment=payment)

        if auto_save:
            payment.save()
            receipt.save()

        return payment, receipt

    def complete_post_invoice(self, invoice: Invoice, invoice_reference: InvoiceReference) -> None:
        """Complete any post invoice activities if needed."""
        # Publish message to the queue with payment token, so that they can release records on their side.
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
    def create_invoice_reference(invoice: InvoiceModel, invoice_number: str,
                                 reference_number: str) -> InvoiceReferenceModel:
        """Create an invoice reference record."""
        if not (invoice_reference := InvoiceReferenceModel
                .find_any_active_reference_by_invoice_number(invoice_number)):
            invoice_reference = InvoiceReferenceModel()

        invoice_reference.invoice_id = invoice.id
        invoice_reference.invoice_number = invoice_number
        invoice_reference.reference_number = reference_number
        invoice_reference.status_code = InvoiceReferenceStatus.ACTIVE.value

        return invoice_reference

    @staticmethod
    def create_receipt(invoice: InvoiceModel, payment: PaymentModel) -> ReceiptModel:
        """Create a receipt record for an invoice payment."""
        receipt: ReceiptModel = ReceiptModel(receipt_date=payment.payment_date,
                                             receipt_amount=payment.paid_amount,
                                             invoice_id=invoice.id,
                                             receipt_number=payment.receipt_number)
        return receipt

    @classmethod
    @user_context
    def create_shortname_refund(cls, request: Dict[str, str], **kwargs) -> Dict[str, str]:
        # pylint: disable=too-many-locals
        """Create refund."""
        shortname_id = get_str_by_path(request, 'shortNameId')
        shortname = get_str_by_path(request, 'shortName')
        amount = get_str_by_path(request, 'refundAmount')
        comment = get_str_by_path(request, 'comment')

        current_app.logger.debug(f'Starting shortname refund : {shortname_id}')

        refund: EFTRefundModel = EFTRefundModel(short_name_id=shortname_id,
                                                refund_amount=amount,
                                                cas_supplier_number=get_str_by_path(request, 'casSupplierNum'),
                                                refund_email=get_str_by_path(request, 'refundEmail'),
                                                comment=comment)
        refund.status = EFTCreditInvoiceStatus.PENDING_REFUND
        recipients = EFTRefundEmailList.find_all_emails()

        subject = f'Pending Refund Request for Short Name {shortname}'

        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root_dir = os.path.dirname(current_dir)
        templates_dir = os.path.join(project_root_dir, 'templates')
        env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)
        template = env.get_template('eft_refund_notification.html')

        url = (f"{current_app.config.get('AUTH_WEB_URL')}/account/"
               'settings/transactions')

        params = {
            'shortname': shortname,
            'refundAmount': amount,
            'comment': comment,
            'url': url
        }
        html_body = template.render(params)

        send_email(recipients, subject, html_body, **kwargs)
        refund.save()
