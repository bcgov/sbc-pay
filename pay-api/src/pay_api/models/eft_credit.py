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
from datetime import datetime
from sqlalchemy import ForeignKey

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
            'short_name_id',
            'payment_account_id',
            'remaining_amount'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    amount = db.Column(db.Numeric(19, 2), nullable=False)
    remaining_amount = db.Column(db.Numeric(19, 2), nullable=False)
    created_on = db.Column('created_on', db.DateTime, nullable=True, default=datetime.now)

    eft_file_id = db.Column(db.Integer, ForeignKey('eft_files.id'), nullable=False)
    short_name_id = db.Column(db.Integer, ForeignKey('eft_short_names.id'), nullable=False)
    payment_account_id = db.Column(db.Integer, ForeignKey('payment_accounts.id'), nullable=True, index=True)

    @classmethod
    def find_by_payment_account_id(cls, payment_account_id: int):
        """Find EFT Credit by payment account id."""
        return cls.query.filter_by(payment_account_id=payment_account_id).all()
