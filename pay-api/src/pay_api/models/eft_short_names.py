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
"""Model to handle EFT TDI17 short name to BCROS account mapping."""

from datetime import datetime

from .base_model import BaseModel
from .db import db


class EFTShortnames(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages the EFT short name to auth account mapping."""

    __tablename__ = 'eft_short_names'
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
            'auth_account_id',
            'created_on',
            'short_name'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    auth_account_id = db.Column('auth_account_id', db.DateTime, nullable=True, index=True)
    created_on = db.Column('created_on', db.DateTime, nullable=False, default=datetime.now)
    short_name = db.Column('short_name', db.String, nullable=False, index=True)
