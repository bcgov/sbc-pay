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
from sbc_common_components.tracing.db_tracing import DBTracing
from sqlalchemy import event
from sqlalchemy.engine import Engine

from .corp_type import CorpType, CorpTypeSchema
from .db import db, ma
from .fee_code import FeeCode, FeeCodeSchema
from .fee_schedule import FeeSchedule, FeeScheduleSchema
from .filing_type import FilingType, FilingTypeSchema
from .payment_account import PaymentAccount, PaymentAccountSchema  # noqa: I001
from .invoice import Invoice, InvoiceSchema
from .invoice_reference import InvoiceReference, InvoiceReferenceSchema
from .payment import Payment, PaymentSchema
from .payment_line_item import PaymentLineItem, PaymentLineItemSchema
from .payment_method import PaymentMethod, PaymentMethodSchema
from .payment_transaction import PaymentTransaction, PaymentTransactionSchema
from .receipt import Receipt, ReceiptSchema
from .status_code import StatusCode, StatusCodeSchema


event.listen(Engine, 'before_cursor_execute', DBTracing.query_tracing)
