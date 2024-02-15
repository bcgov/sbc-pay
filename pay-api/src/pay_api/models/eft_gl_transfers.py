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
"""Model to track EFT GL transfers."""

from datetime import datetime

from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db


class EFTGLTransfer(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages the file data for EFT transactions."""

    __tablename__ = 'eft_gl_transfers'
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
            'created_on',
            'invoice_id',
            'is_processed',
            'processed_on',
            'short_name_id',
            'source_gl',
            'target_gl',
            'transfer_amount',
            'transfer_type',
            'transfer_date'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Intended to be populated based on TDI17 date for GL Transfers or payment date of an invoice for distributions
    transfer_date = db.Column('transfer_date', db.DateTime, nullable=False, default=datetime.now, index=True)
    transfer_type = db.Column('transfer_type', db.String(50), nullable=False)
    transfer_amount = db.Column(db.Numeric(19, 2), nullable=False)
    source_gl = db.Column('source_gl', db.String(50), nullable=False)
    target_gl = db.Column('target_gl', db.String(50), nullable=False)
    is_processed = db.Column('is_processed', db.Boolean(), nullable=False, default=False)
    processed_on = db.Column('processed_on', db.DateTime, nullable=True)
    created_on = db.Column('created_on', db.DateTime, nullable=False, default=datetime.now)
    invoice_id = db.Column(db.Integer, ForeignKey('invoices.id'), nullable=True)
    short_name_id = db.Column(db.Integer, ForeignKey('eft_short_names.id'), nullable=False)
