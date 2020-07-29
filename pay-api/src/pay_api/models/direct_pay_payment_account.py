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
"""Model to handle all operations related to Direct Pay Account data."""
from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db, ma
from .payment_account import PaymentAccount


class DirectPayPaymentAccount(BaseModel):
    """This class manages all of the base data about Direct Pay Account."""

    __tablename__ = 'direct_pay_payment_account'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    corp_number = db.Column(db.String(20), nullable=True)
    corp_type_code = db.Column(db.String(10), ForeignKey('corp_type.code'), nullable=True)

    account_id = db.Column(db.Integer, ForeignKey('payment_account.id'), nullable=True,
                           index=True)  # payment account id

    @classmethod
    def find_by_id(cls, identifier: int):
        """Return a Account by id for direct payment."""
        return cls.query.get(identifier)

    @classmethod
    def find_by_corp_number_and_corp_type_and_account_id(cls, corp_number: str, corp_type: str, account_id):
        """Given a corp_number and corp_type, this will return payment account for direct payment."""
        account = None
        # find the account using corp number and type
        if corp_number and corp_type:
            query = cls.query.filter_by(corp_number=corp_number). \
                filter_by(corp_type_code=corp_type). \
                join(PaymentAccount).filter(PaymentAccount.auth_account_id == account_id)

            account = query.one_or_none()

        return account


class DirectPayAccountSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Internal Payment System Account."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = DirectPayPaymentAccount
