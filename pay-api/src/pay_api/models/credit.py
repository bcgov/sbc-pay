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
"""Model to handle all operations related to Credit data."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, ForeignKey

from .base_model import BaseModel
from .db import db, ma


class Credit(BaseModel):  # pylint:disable=too-many-instance-attributes
    """This class manages all of the base data about Credit."""

    __tablename__ = 'credits'
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
            'amount',
            'cfs_identifier',
            'created_on',
            'details',
            'is_credit_memo',
            'remaining_amount'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    cfs_identifier = db.Column(db.String(50), nullable=True, index=True)
    is_credit_memo = db.Column(Boolean(), default=False)
    amount = db.Column(db.Float, nullable=False)
    remaining_amount = db.Column(db.Float, nullable=False)
    details = db.Column(db.String(200), nullable=True)
    created_on = db.Column('created_on', db.DateTime, nullable=True, default=datetime.now(tz=timezone.utc))

    account_id = db.Column(db.Integer, ForeignKey('payment_accounts.id'), nullable=True, index=True)

    @classmethod
    def find_by_cfs_identifier(cls, cfs_identifier: str, credit_memo: bool = False):
        """Find Credit by cfs identifier."""
        return cls.query.filter_by(cfs_identifier=cfs_identifier).filter_by(is_credit_memo=credit_memo).one_or_none()


class CreditSchema(ma.SQLAlchemyAutoSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Credit."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Credit
        load_instance = True
