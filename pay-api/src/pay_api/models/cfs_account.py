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
"""Model to handle all operations related to PayBC Account data."""
from __future__ import annotations
from typing import List
from flask import current_app
from sql_versioning import Versioned
from sqlalchemy import ForeignKey
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship
from sqlalchemy.types import String
from sqlalchemy_utils.types.encrypted.encrypted_type import AesEngine, StringEncryptedType

from pay_api.utils.enums import CfsAccountStatus

from .base_schema import BaseSchema
from .base_model import BaseModel
from .db import db


class CfsAccount(Versioned, BaseModel):  # pylint:disable=too-many-instance-attributes
    """This class manages all of the base data about PayBC Account."""

    __tablename__ = 'cfs_accounts'
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
            'bank_account_number',
            'bank_number',
            'bank_branch_number',
            'cfs_account',
            'cfs_party',
            'cfs_site',
            'contact_party',
            'payment_instrument_number',
            'payment_method',
            'status'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    cfs_account = db.Column(db.String(50), nullable=True, index=True)
    cfs_party = db.Column(db.String(50), nullable=True)
    cfs_site = db.Column(db.String(50), nullable=True)
    payment_instrument_number = db.Column(db.String(50), nullable=True)
    contact_party = db.Column(db.String(50), nullable=True)
    bank_number = db.Column(db.String(50), nullable=True, index=True)
    bank_branch_number = db.Column(db.String(50), nullable=True, index=True)
    payment_method = db.Column(db.String(15), ForeignKey('payment_methods.code'), nullable=True)

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
    def find_effective_or_latest_by_payment_method(cls, account_id: str, payment_method: str) -> CfsAccount:
        """Return effective cfs account by payment_method that isn't inactive or latest by payment_method.

        An example of this is switching from PAD/EFT to DRAWDOWN.
        """
        return cls.find_effective_by_payment_method(account_id, payment_method) or \
            cls.find_latest_by_payment_method(account_id, payment_method)

    @classmethod
    def find_effective_by_payment_method(cls, account_id: str, payment_method: str) -> CfsAccount:
        """Return effective cfs account by payment_method that isn't inactive."""
        return CfsAccount.query.filter(CfsAccount.account_id == account_id,
                                       CfsAccount.payment_method == payment_method,
                                       CfsAccount.status != CfsAccountStatus.INACTIVE.value).one_or_none()

    @classmethod
    def find_latest_by_payment_method(cls, account_id: str, payment_method: str) -> CfsAccount:
        """Return latest CFS account by account_id and payment_method."""
        return CfsAccount.query.filter(CfsAccount.account_id == account_id,
                                       CfsAccount.payment_method == payment_method) \
            .order_by(CfsAccount.id.desc()) \
            .first()

    @classmethod
    def find_latest_account_by_account_id(cls, account_id: str):
        """Return a frozen account by account_id, and return the record with the highest id."""
        return CfsAccount.query.filter(
            CfsAccount.account_id == account_id).order_by(CfsAccount.id.desc()).one_or_none()

    @classmethod
    def find_by_account_id(cls, account_id: str) -> List[CfsAccount]:
        """Return a Account by id."""
        return CfsAccount.query.filter(CfsAccount.account_id == account_id).all()

    @classmethod
    def find_all_pending_accounts(cls):
        """Find all pending accounts to be created in CFS."""
        return cls.query.filter_by(status=CfsAccountStatus.PENDING.value).all()

    @classmethod
    def find_all_accounts_with_status(cls, status: str):
        """Find all pending accounts to be created in CFS."""
        return cls.query.filter_by(status=status).all()


class CfsAccountSchema(BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the CFS Account."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = CfsAccount
