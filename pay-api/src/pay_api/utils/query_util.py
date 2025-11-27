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
"""Utility for common query operations."""

from sqlalchemy import case, func
from sqlalchemy.sql.selectable import Join

from pay_api.models import PaymentAccount as PaymentAccountModel


class QueryUtils:
    """Used to provide common query operations."""

    @staticmethod
    def statement_has_join(stmt, target_table):
        """Check if statement already has a join with target table."""
        for from_obj in stmt.get_final_froms():
            if isinstance(from_obj, Join):
                if from_obj.right == target_table or from_obj.left == target_table:
                    return True
            elif from_obj == target_table:
                return True
        return False

    @staticmethod
    def add_payment_account_name_columns(query):
        """Add payment account name and branch to query select columns."""
        return query.add_columns(
            case(
                (
                    PaymentAccountModel.name.like("%-" + PaymentAccountModel.branch_name),
                    func.replace(
                        PaymentAccountModel.name,
                        "-" + PaymentAccountModel.branch_name,
                        "",
                    ),
                ),
                else_=PaymentAccountModel.name,
            ).label("account_name"),
            PaymentAccountModel.branch_name.label("account_branch"),
        )
