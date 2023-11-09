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

from marshmallow import fields

from .base_model import VersionedModel
from .base_schema import BaseSchema
from .db import db


class EFTShortnames(VersionedModel):  # pylint: disable=too-many-instance-attributes
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

    @classmethod
    def find_by_short_name(cls, short_name: str):
        """Find by eft short name."""
        return cls.query.filter_by(short_name=short_name).one_or_none()

    @classmethod
    def find_all_short_names(cls, include_all: bool, page: int, limit: int):
        """Return eft short names."""
        query = db.session.query(EFTShortnames)

        if not include_all:
            query = query.filter(EFTShortnames.auth_account_id.is_(None))

        query = query.order_by(EFTShortnames.short_name.asc())
        pagination = query.paginate(per_page=limit, page=page)
        return pagination.items, pagination.total


class EFTShortnameSchema(BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the EFT Short name."""

    class Meta(BaseSchema.Meta):  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = EFTShortnames

    auth_account_id = fields.String(data_key='account_id')
