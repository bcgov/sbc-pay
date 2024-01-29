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

from sqlalchemy import func

from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTTransaction as EFTTransactionModel
from pay_api.models import EFTTransactionSchema, db
from pay_api.utils.converter import Converter
from pay_api.utils.enums import EFTProcessStatus


@dataclass
class EFTTransactionSearch:
    """Used for searching EFT transaction records."""

    page: Optional[int] = 1
    limit: Optional[int] = 10


class EFTTransactions:
    """Service to manage EFT Transactions."""

    @staticmethod
    def get_remaining_credits(short_name_id: int):
        """Return the remaining credit for a short name."""
        return db.session.query(func.sum(EFTCreditModel.remaining_amount))\
            .filter(EFTCreditModel.short_name_id == short_name_id)\
            .group_by(EFTCreditModel.short_name_id).scalar()

    @classmethod
    def search(cls, short_name_id: int,
               search_criteria: EFTTransactionSearch = EFTTransactionSearch()) -> [EFTTransactionModel]:
        """Return EFT Transfers by search criteria."""
        query = db.session.query(EFTTransactionModel) \
            .filter(EFTTransactionModel.short_name_id == short_name_id) \
            .filter(EFTTransactionModel.status_code == EFTProcessStatus.COMPLETED.value)\
            .order_by(EFTTransactionModel.transaction_date.desc())

        pagination = query.paginate(per_page=search_criteria.limit,
                                    page=search_criteria.page)

        transaction_list = [EFTTransactionSchema.from_row(transaction) for transaction in pagination.items]
        converter = Converter()
        transaction_list = converter.unstructure(transaction_list)

        remaining_credit = cls.get_remaining_credits(short_name_id)
        remaining_credit = float(remaining_credit) if remaining_credit else 0

        return {
            'page': search_criteria.page,
            'limit': search_criteria.limit,
            'items': transaction_list,
            'total': pagination.total,
            'remaining_credit': remaining_credit
        }
