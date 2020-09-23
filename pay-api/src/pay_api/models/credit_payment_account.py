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
"""Model to handle all operations related to PayBC Account data."""
from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db, ma
from .payment_account import PaymentAccount


class CreditPaymentAccount(BaseModel):
    """This class manages all of the base data about PayBC Account."""

    __tablename__ = 'credit_payment_account'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    corp_number = db.Column(db.String(20), nullable=True)
    corp_type_code = db.Column(db.String(10), ForeignKey('corp_type.code'), nullable=True)

    paybc_account = db.Column(db.String(50), nullable=True, index=True)
    paybc_party = db.Column(db.String(50), nullable=True)
    paybc_site = db.Column(db.String(50), nullable=True)

    account_id = db.Column(db.Integer, ForeignKey('payment_account.id'), nullable=True, index=True)

    @classmethod
    def find_by_corp_number_and_corp_type_and_auth_account_id(cls, corp_number: str,
                                                              corp_type: str,
                                                              auth_account_id: str
                                                              ):
        """Given a corp_number, corp_type and payment_system, this will return payment account."""
        query = cls.query.filter_by(corp_type_code=corp_type)
        if corp_number:
            query = query.filter_by(corp_number=corp_number)

        return query.join(PaymentAccount).filter(PaymentAccount.auth_account_id == str(auth_account_id)).one_or_none()

    @classmethod
    def find_by_corp_number(cls, corp_number: str):
        """Find all payment accounts by corp number."""
        return cls.query.filter_by(corp_number=corp_number).all()


class CreditPaymentAccountSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Credit Payment System Account."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = CreditPaymentAccount
