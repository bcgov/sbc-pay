# Copyright © 2019 Province of British Columbia
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

"""This exports all of the models and schemas used by the application."""
from sqlalchemy import event  # noqa: I001
from sqlalchemy.engine import Engine  # noqa: I001, I003, I004
from sbc_common_components.tracing.db_tracing import DBTracing  # noqa: I001, I004

from .fee_code import FeeCode, FeeCodeSchema  # noqa: I001
from .corp_type import CorpType, CorpTypeSchema  # noqa: I001
from .db import db, ma  # noqa: I001
from .filing_type import FilingType, FilingTypeSchema
from .distribution_code import DistributionCode, DistributionCodeLink
from .fee_schedule import FeeSchedule, FeeScheduleSchema
from .error_code import ErrorCode, ErrorCodeSchema
from .payment_account import PaymentAccount, PaymentAccountSchema  # noqa: I001
from .bcol_payment_account import BcolPaymentAccount, BcolPaymentAccountSchema  # noqa: I001
from .credit_payment_account import CreditPaymentAccount, CreditPaymentAccountSchema  # noqa: I001
from .internal_payment_account import InternalPaymentAccount, InternalPaymentAccountSchema
from .invoice import Invoice, InvoiceSchema
from .invoice_reference import InvoiceReference, InvoiceReferenceSchema
from .payment import Payment, PaymentSchema
from .payment_line_item import PaymentLineItem, PaymentLineItemSchema
from .payment_method import PaymentMethod, PaymentMethodSchema
from .payment_transaction import PaymentTransaction, PaymentTransactionSchema
from .receipt import Receipt, ReceiptSchema
from .payment_status_code import PaymentStatusCode, PaymentStatusCodeSchema
from .invoice_status_code import InvoiceStatusCode, InvoiceStatusCodeSchema
from .transaction_status_code import TransactionStatusCode, TransactionStatusCodeSchema
from .invoice_reference_status_code import InvoiceReferenceStatusCode, InvoiceReferenceStatusCodeSchema
from .line_item_status_code import LineItemStatusCode, LineItemStatusCodeSchema


event.listen(Engine, 'before_cursor_execute', DBTracing.query_tracing)
