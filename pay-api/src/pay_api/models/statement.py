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
"""Model to handle statements data."""
from datetime import date


from sqlalchemy import ForeignKey

from .payment_account import PaymentAccount

from .base_model import BaseModel
from .db import db, ma


class Statement(BaseModel):
    """This class manages the statements related data."""

    __tablename__ = 'statement'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    frequency = db.Column(db.String(50), nullable=True, index=True)
    payment_account_id = db.Column(db.Integer, ForeignKey('payment_account.id'), nullable=True, index=True)
    from_date = db.Column(db.Date, default=date.today(), nullable=False)
    to_date = db.Column(db.Date, default=None, nullable=False)
    status = db.Column(db.String(50), nullable=True, index=True)

    @classmethod
    def find_all_statements_for_account(cls, account_id: str, page, limit):
        """Return all active statements for an account."""
        # TODO is status needed.If needed , does it need a separate table to store statuses
        query = cls.query.filter(Statement.status == 'ACTIVE'). \
            join(PaymentAccount).filter(PaymentAccount.auth_account_id == account_id)

        query = query.order_by(Statement.id)
        pagination = query.paginate(per_page=limit, page=page)
        return pagination.items, pagination.total


class StatementSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Statements."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Statement
        exclude = ['status']
