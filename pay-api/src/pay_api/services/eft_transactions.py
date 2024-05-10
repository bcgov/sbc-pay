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
"""Service to manage EFT Transactions."""
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import Float, and_, case, cast, desc, func, literal, null

from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTCreditInvoiceLink as EFTCreditInvoiceLinkModel
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.models import EFTTransactionSchema
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import Statement as StatementModel
from pay_api.models import StatementInvoices as StatementInvoicesModel
from pay_api.models import db
from pay_api.utils.enums import EFTCreditInvoiceStatus, EFTFileLineType, EFTProcessStatus
from pay_api.utils.util import unstructure_schema_items


@dataclass
class EFTTransactionSearch:
    """Used for searching EFT transaction records."""

    page: Optional[int] = 1
    limit: Optional[int] = 10


class EFTTransactions:
    """Service to manage EFT Transactions."""

    @staticmethod
    def get_account_name():
        """Return case statement for deriving payment account name."""
        return case(
            (PaymentAccountModel.name.like('%-' + PaymentAccountModel.branch_name),
             func.replace(PaymentAccountModel.name, '-' + PaymentAccountModel.branch_name, '')
             ), else_=PaymentAccountModel.name).label('account_name')

    @staticmethod
    def get_funds_received_query():
        """Return the EFT transaction funds received."""
        # Null valued columns are defined for the purposes of unioning with funds applied query
        # We don't need the account information and there will be no statement for EFT Transactions received
        # through a TDI17
        return db.session.query(EFTTransactionModel.id.label('transaction_id'),
                                EFTTransactionModel.short_name_id,
                                EFTTransactionModel.deposit_date.label('transaction_date'),
                                (cast(
                                    EFTTransactionModel.deposit_amount_cents, Float) / 100
                                 ).label('transaction_amount'),
                                literal('Funds Received').label('transaction_description'),
                                null().label('statement_id'),
                                null().label('auth_account_id'),
                                null().label('account_name'),
                                null().label('account_branch'))

    @staticmethod
    def get_funds_applied_query():
        """Return the EFT transaction funds applied by account statement."""
        return (db.session.query(StatementModel.payment_account_id,
                                 EFTCreditModel.short_name_id,
                                 func.max(InvoiceModel.payment_date).label('transaction_date'),
                                 StatementInvoicesModel.statement_id,
                                 func.sum(EFTCreditInvoiceLinkModel.amount).label('paid_amount'))
                .join(InvoiceModel, InvoiceModel.id == StatementInvoicesModel.invoice_id)
                .join(StatementModel, StatementModel.id == StatementInvoicesModel.statement_id)
                .join(EFTCreditInvoiceLinkModel,
                      and_(EFTCreditInvoiceLinkModel.invoice_id == StatementInvoicesModel.invoice_id,
                           EFTCreditInvoiceLinkModel.status_code == EFTCreditInvoiceStatus.COMPLETED.value))
                .join(EFTCreditModel, EFTCreditModel.id == EFTCreditInvoiceLinkModel.eft_credit_id)
                .group_by(StatementModel.payment_account_id,
                          EFTCreditModel.short_name_id,
                          StatementInvoicesModel.statement_id)
                )

    @classmethod
    def search(cls, short_name_id: int,
               search_criteria: EFTTransactionSearch = EFTTransactionSearch()) -> [EFTTransactionModel]:
        """Return EFT Transfers by search criteria."""
        funds_received_query = (cls.get_funds_received_query()
                                .filter(EFTTransactionModel.short_name_id == short_name_id)
                                .filter(EFTTransactionModel.status_code == EFTProcessStatus.COMPLETED.value)
                                .filter(EFTTransactionModel.line_type == EFTFileLineType.TRANSACTION.value))

        funds_applied_subquery = cls.get_funds_applied_query().subquery()
        funds_applied_query = (db.session.query(null().label('transaction_id'),
                                                funds_applied_subquery.c.short_name_id,
                                                funds_applied_subquery.c.transaction_date,
                                                funds_applied_subquery.c.paid_amount.label('transaction_amount'),
                                                literal('Statement Paid').label('transaction_description'),
                                                funds_applied_subquery.c.statement_id,
                                                PaymentAccountModel.auth_account_id,
                                                cls.get_account_name(),
                                                PaymentAccountModel.branch_name)
                               .join(funds_applied_subquery,
                                     and_(funds_applied_subquery.c.payment_account_id == PaymentAccountModel.id,
                                          funds_applied_subquery.c.short_name_id == short_name_id)))

        union_query = funds_received_query.union(funds_applied_query)
        union_query = union_query.order_by(desc('transaction_date'))

        pagination = union_query.paginate(per_page=search_criteria.limit,
                                          page=search_criteria.page)

        transaction_list = unstructure_schema_items(EFTTransactionSchema, pagination.items)

        return {
            'page': search_criteria.page,
            'limit': search_criteria.limit,
            'items': transaction_list,
            'total': pagination.total
        }
