# Copyright © 2023 Province of British Columbia
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
"""Model to handle all operations related to EFT Credits data."""
from datetime import datetime, timezone
from typing import List, Self
from decimal import Decimal

from sqlalchemy import ForeignKey, func

from .base_model import BaseModel
from .db import db


class EFTCredit(BaseModel):  # pylint:disable=too-many-instance-attributes
    """This class manages all of the base data for EFT credits."""

    __tablename__ = 'eft_credits'
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
            'amount',
            'created_on',
            'eft_file_id',
            'eft_transaction_id',
            'short_name_id',
            'payment_account_id',
            'remaining_amount'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    amount = db.Column(db.Numeric(19, 2), nullable=False)
    remaining_amount = db.Column(db.Numeric(19, 2), nullable=False)
    created_on = db.Column('created_on', db.DateTime, nullable=False, default=lambda: datetime.now(tz=timezone.utc))

    eft_file_id = db.Column(db.Integer, ForeignKey('eft_files.id'), nullable=False)
    short_name_id = db.Column(db.Integer, ForeignKey('eft_short_names.id'), nullable=False)
    eft_transaction_id = db.Column(db.Integer, ForeignKey('eft_transactions.id'), nullable=True)

    @classmethod
    def find_by_payment_account_id(cls, payment_account_id: int):
        """Find EFT Credit by payment account id."""
        return cls.query.filter_by(payment_account_id=payment_account_id).all()

    @classmethod
    def get_eft_credit_balance(cls, short_name_id: int) -> Decimal:
        """Calculate pay account eft balance by account id."""
        result = cls.query.with_entities(func.sum(cls.remaining_amount).label('credit_balance')) \
            .filter(cls.short_name_id == short_name_id) \
            .group_by(cls.short_name_id) \
            .one_or_none()

        return Decimal(result.credit_balance) if result else 0

    @classmethod
    def get_eft_credits(cls, short_name_id: int) -> List[Self]:
        """Get EFT Credits with a remaining amount."""
        return (cls.query
                .filter(EFTCredit.remaining_amount > 0)
                .filter(EFTCredit.short_name_id == short_name_id)
                .order_by(EFTCredit.created_on.asc())
                .all())
