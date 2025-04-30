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

"""This exports all of the models and schemas used by the application."""
from sbc_common_components.tracing.db_tracing import DBTracing  # noqa: I001, I004
from sqlalchemy import event  # noqa: I001
from sqlalchemy.engine import Engine  # noqa: I001, I003, I004

from .account_fee import AccountFee, AccountFeeSchema
from .cas_settlement import CasSettlement
from .cfs_account import CfsAccount, CfsAccountSchema
from .cfs_account_status_code import CfsAccountStatusCode, CfsAccountStatusCodeSchema
from .cfs_credit_invoices import CfsCreditInvoices
from .corp_type import CorpType, CorpTypeSchema  # noqa: I001
from .credit import Credit
from .custom_query import CustomQuery
from .db import db, ma  # noqa: I001
from .disbursement_status_code import DisbursementStatusCode
from .distribution_code import DistributionCode, DistributionCodeLink
from .eft_credit import EFTCredit
from .eft_credit_invoice_link import EFTCreditInvoiceLink
from .eft_file import EFTFile
from .eft_process_status_code import EFTProcessStatusCode
from .eft_refund import EFTRefund
from .eft_short_name_links import EFTShortnameLinks, EFTShortnameLinkSchema
from .eft_short_names import EFTShortnames, EFTShortnameSchema, EFTShortnameSummarySchema
from .eft_short_names_historical import EFTShortnameHistorySchema, EFTShortnamesHistorical
from .eft_transaction import EFTTransaction, EFTTransactionSchema
from .ejv_file import EjvFile
from .ejv_header import EjvHeader
from .ejv_link import EjvLink
from .error_code import ErrorCode, ErrorCodeSchema
from .fee_code import FeeCode, FeeCodeSchema  # noqa: I001
from .fee_schedule import FeeDetailsSchema, FeeSchedule, FeeScheduleSchema
from .filing_type import FilingType, FilingTypeSchema
from .invoice import Invoice, InvoiceSchema, InvoiceSearchModel
from .invoice_reference import InvoiceReference, InvoiceReferenceSchema
from .invoice_reference_status_code import InvoiceReferenceStatusCode, InvoiceReferenceStatusCodeSchema
from .invoice_status_code import InvoiceStatusCode, InvoiceStatusCodeSchema
from .line_item_status_code import LineItemStatusCode, LineItemStatusCodeSchema
from .non_sufficient_funds import NonSufficientFunds, NonSufficientFundsSchema
from .notification_status_code import NotificationStatusCode, NotificationStatusCodeSchema
from .partner_disbursements import PartnerDisbursements
from .payment import Payment, PaymentSchema
from .payment_account import PaymentAccount, PaymentAccountSchema, PaymentAccountSearchModel  # noqa: I001
from .payment_line_item import PaymentLineItem, PaymentLineItemSchema
from .payment_method import PaymentMethod, PaymentMethodSchema
from .payment_status_code import PaymentStatusCode, PaymentStatusCodeSchema
from .payment_transaction import PaymentTransaction, PaymentTransactionSchema
from .receipt import Receipt, ReceiptSchema
from .refund import Refund
from .refunds_partial import RefundPartialLine, RefundsPartial
from .routing_slip import RoutingSlip, RoutingSlipSchema
from .routing_slip_status_code import RoutingSlipStatusCode, RoutingSlipStatusCodeSchema
from .statement import Statement, StatementDTO, StatementSchema
from .statement_invoices import StatementInvoices, StatementInvoicesSchema  # noqa: I005
from .statement_recipients import StatementRecipients, StatementRecipientsSchema
from .statement_settings import StatementSettings, StatementSettingsSchema
from .transaction_status_code import TransactionStatusCode, TransactionStatusCodeSchema

from .comment import Comment, CommentSchema  # isort: skip - This has to be at the bottom otherwise FeeSchedule errors

event.listen(Engine, "before_cursor_execute", DBTracing.query_tracing)
