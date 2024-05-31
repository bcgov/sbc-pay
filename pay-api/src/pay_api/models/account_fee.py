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
"""Model to handle all operations related to Fee related to accounts."""
from __future__ import annotations

from marshmallow import fields, post_dump
from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sql_versioning import Versioned

from .audit import Audit
from .base_model import BaseModel
from .base_schema import BaseSchema
from .corp_type import CorpType
from .db import db
from .fee_code import FeeCode
from .payment_account import PaymentAccount


class AccountFee(Audit, Versioned, BaseModel):
    """This class manages all of the base data about Account Fees."""

    __tablename__ = 'account_fees'
    # this mapper is used so that new and old versions of the service can be run simultaneously,
    # making rolling upgrades easier
    # This is used by SQLAlchemy to explicitly define which fields we're interested
    # so it doesn't freak out and say it can't map the structure if other fields are present.
    # This could occur from a failed deploy or during an upgrade.
    # The other option is to tell SQLAlchemy to ignore differences, but that is ambiguous
    # and can interfere with Alembic upgrades.
    #
    # NOTE: please keep mapper names in alpha-order, easier to track that way
    #       Exception, id is always first, _fields first
    __mapper_args__ = {
        'include_properties': [
            'id',
            'account_id',
            'apply_filing_fees',
            'created_by',
            'created_name',
            'created_on',
            'product',
            'service_fee_code',
            'updated_by',
            'updated_name',
            'updated_on'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    account_id = db.Column(db.Integer, ForeignKey('payment_accounts.id'), nullable=True, index=True)
    apply_filing_fees = db.Column('apply_filing_fees', Boolean(), default=True)
    service_fee_code = db.Column(db.String(10), ForeignKey('fee_codes.code'), nullable=True)
    product = db.Column(db.String(20), nullable=True)

    service_fee = relationship(FeeCode, foreign_keys=[service_fee_code], lazy='joined', innerjoin=False)

    @classmethod
    def find_by_account_id(cls, account_id: str):
        """Return by account id."""
        return AccountFee.query.filter(AccountFee.account_id == account_id).all()

    @classmethod
    def find_by_account_id_and_product(cls, account_id: str, product: str):
        """Return by account id and product."""
        return AccountFee.query.filter(AccountFee.account_id == account_id, AccountFee.product == product).one_or_none()

    @classmethod
    def find_by_auth_account_id_and_corp_type(cls, account_id: str, corp_type_code: str) -> AccountFee:
        """Return by auth account id and corp type code."""
        account_fee: AccountFee = None
        if account_id and corp_type_code:
            account_fee = db.session.query(AccountFee) \
                .join(CorpType, CorpType.product == AccountFee.product) \
                .outerjoin(PaymentAccount, PaymentAccount.id == AccountFee.account_id) \
                .filter(CorpType.code == corp_type_code) \
                .filter(PaymentAccount.auth_account_id == account_id).one_or_none()
        return account_fee


class AccountFeeSchema(BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the CFS Account."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = AccountFee
        exclude = ['service_fee']

    @post_dump(pass_many=True)
    def _remove_empty(self, data, many):
        return data

    service_fee_code = fields.String(data_key='service_fee_code')
