# Copyright © 2022 Province of British Columbia
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
"""Class to record the settlement file information for a payment."""

from datetime import datetime, timezone

from pay_api.models.base_model import BaseModel
from .db import db


class CasSettlement(BaseModel):  # pylint: disable=too-few-public-methods
    """This class keeps track of the settlements from CAS, usually provided in CSV format."""

    __tablename__ = "cas_settlements"
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
    __mapper_args__ = {"include_properties": ["id", "file_name", "processed_on", "received_on"]}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    received_on = db.Column(
        "received_on",
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
    )
    file_name = db.Column(db.String, nullable=False)
    processed_on = db.Column("processed_on", db.DateTime, nullable=True)
