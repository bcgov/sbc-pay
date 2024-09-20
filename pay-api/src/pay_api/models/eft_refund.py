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
"""Model to handle EFT REFUNDS, this is picked up by the AP job to mail out."""
from datetime import datetime, timezone

from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db


class EFTRefund(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages the file data for EFT Refunds."""

    __tablename__ = 'eft_refunds'
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
            'auth_account_id',
            'cas_supplier_number',
            'comment',
            'created_by',
            'created_on',
            'decline_reason',
            'id',
            'refund_amount',
            'refund_email',
            'short_name_id',
            'status',
            'updated_by_name',
            'updated_by',
            'updated_on'
        ]
    }

    cas_supplier_number = db.Column(db.String(), nullable=False)
    comment = db.Column(db.String(), nullable=False)
    decline_reason = db.Column(db.String(), nullable=True)
    created_by = db.Column('created_by', db.String(100), nullable=True)
    created_on = db.Column('created_on', db.DateTime, nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    refund_amount = db.Column(db.Numeric(), nullable=False)
    refund_email = db.Column(db.String(100), nullable=False)
    short_name_id = db.Column(db.Integer, ForeignKey('eft_short_names.id'), nullable=False)
    status = db.Column(db.String(25), nullable=True)
    updated_by = db.Column('updated_by', db.String(100), nullable=True)
    updated_by_name = db.Column('updated_by_name', db.String(100), nullable=True)
    updated_on = db.Column('updated_on', db.DateTime, nullable=True)
