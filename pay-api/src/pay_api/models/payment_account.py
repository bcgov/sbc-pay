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
"""Model to handle all operations related to Payment Account data."""
from sqlalchemy import ForeignKey

from pay_api.utils.enums import PaymentSystem

from .base_model import BaseModel
from .db import db, ma


class PaymentAccount(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Payment Account."""

    __tablename__ = 'payment_account'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    corp_number = db.Column(db.String(20), nullable=True)
    corp_type_code = db.Column(db.String(10), ForeignKey('corp_type.code'), nullable=True)
    payment_system_code = db.Column(db.String(10), ForeignKey('payment_system.code'), nullable=False)
    account_number = db.Column(db.String(50), nullable=True, index=True)
    party_number = db.Column(db.String(50), nullable=True)
    site_number = db.Column(db.String(50), nullable=True)
    bcol_user_id = db.Column(db.String(50), nullable=True, index=True)
    bcol_account_id = db.Column(db.String(50), nullable=True, index=True)
    auth_account_id = db.Column(db.String(50), nullable=True, index=True)

    @classmethod
    def find_by_corp_number_and_corp_type_and_system(cls, corp_number: str,
                                                     corp_type: str,
                                                     payment_system: str
                                                     ):
        """Given a corp_number, corp_type and payment_system, this will return payment account."""
        account = None
        if corp_number and corp_type and payment_system:
            query = cls.query.filter_by(corp_number=corp_number). \
                filter_by(corp_type_code=corp_type). \
                filter_by(payment_system_code=payment_system)

            account = query.one_or_none()

        return account

    @classmethod
    def find_by_bcol_user_id_and_account(cls, bcol_user_id: str, bcol_account_id: str, auth_account_id: str):
        """Given a bcol user id, bcol account id and auth account id, this will return payment account."""
        account = None
        if bcol_user_id and bcol_account_id and auth_account_id:
            query = cls.query.filter_by(bcol_user_id=bcol_user_id). \
                filter_by(bcol_account_id=bcol_account_id). \
                filter_by(auth_account_id=auth_account_id). \
                filter_by(payment_system_code=PaymentSystem.BCOL.value)

            account = query.one_or_none()

        return account

    @classmethod
    def find_by_id(cls, identifier: int):
        """Return a Account by id."""
        return cls.query.get(identifier)


class PaymentAccountSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Payment Account."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = PaymentAccount
