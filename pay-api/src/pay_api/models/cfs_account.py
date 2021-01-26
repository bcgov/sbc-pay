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
from flask import current_app
from sqlalchemy import ForeignKey
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship
from sqlalchemy.types import String
from sqlalchemy_utils.types.encrypted.encrypted_type import AesEngine, StringEncryptedType

from pay_api.utils.enums import CfsAccountStatus
from .base_model import VersionedModel
from .db import db, ma


class CfsAccount(VersionedModel):  # pylint:disable=too-many-instance-attributes
    """This class manages all of the base data about PayBC Account."""

    __tablename__ = 'cfs_accounts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    cfs_account = db.Column(db.String(50), nullable=True, index=True)
    cfs_party = db.Column(db.String(50), nullable=True)
    cfs_site = db.Column(db.String(50), nullable=True)
    payment_instrument_number = db.Column(db.String(50), nullable=True)
    contact_party = db.Column(db.String(50), nullable=True)
    bank_number = db.Column(db.String(50), nullable=True, index=True)
    bank_branch_number = db.Column(db.String(50), nullable=True, index=True)

    status = db.Column(db.String(40), ForeignKey('cfs_account_status_codes.code'), nullable=True)

    account_id = db.Column(db.Integer, ForeignKey('payment_accounts.id'), nullable=True, index=True)

    payment_account = relationship('PaymentAccount', foreign_keys=[account_id], lazy='select')

    @declared_attr
    def bank_account_number(cls):  # pylint:disable=no-self-argument, # noqa: N805
        """Declare attribute for bank account number."""
        return db.Column('bank_account_number', StringEncryptedType(String, cls._get_enc_secret, AesEngine, 'pkcs5'),
                         nullable=True, index=True)

    @staticmethod
    def _get_enc_secret():
        """Return account secret key for encryption."""
        return current_app.config.get('ACCOUNT_SECRET_KEY')

    @classmethod
    def find_effective_by_account_id(cls, account_id: str):
        """Return a Account by id."""
        return CfsAccount.query.filter(CfsAccount.account_id == account_id,
                                       CfsAccount.status != CfsAccountStatus.INACTIVE.value).one_or_none()

    @classmethod
    def find_all_pending_accounts(cls):
        """Find all pending accounts to be created in CFS."""
        return cls.query.filter_by(status=CfsAccountStatus.PENDING.value).all()

    @classmethod
    def find_all_accounts_with_status(cls, status: str):
        """Find all pending accounts to be created in CFS."""
        return cls.query.filter_by(status=status).all()


class CfsAccountSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the CFS Account."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = CfsAccount
