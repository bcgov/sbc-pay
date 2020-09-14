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
from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import relationship

from .base_model import BaseModel
from .db import db, ma


class CfsAccount(BaseModel):
    """This class manages all of the base data about PayBC Account."""

    __tablename__ = 'cfs_account'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    cfs_account = db.Column(db.String(50), nullable=True, index=True)
    cfs_party = db.Column(db.String(50), nullable=True)
    cfs_site = db.Column(db.String(50), nullable=True)
    payment_instrument_number = db.Column(db.String(50), nullable=True)
    contact_party = db.Column(db.String(50), nullable=True)
    bank_name = db.Column(db.String(50), nullable=True, index=True)
    bank_number = db.Column(db.String(50), nullable=True, index=True)
    bank_branch = db.Column(db.String(50), nullable=True, index=True)
    bank_branch_number = db.Column(db.String(50), nullable=True, index=True)
    bank_account_number = db.Column(db.String(50), nullable=True, index=True)

    is_active = db.Column(Boolean(), default=True)

    account_id = db.Column(db.Integer, ForeignKey('payment_account.id'), nullable=True, index=True)

    payment_account = relationship('PaymentAccount', foreign_keys=[account_id], lazy='select')

    @classmethod
    def find_active_by_account_id(cls, account_id: str):
        """Return a Account by id."""
        return cls.query.filter_by(account_id=account_id, is_active=True).one_or_none()


class CfsAccountSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the CFS Account."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = CfsAccount
