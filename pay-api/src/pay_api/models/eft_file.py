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
"""Model to handle EFT file processing."""

from datetime import datetime, timezone

from sqlalchemy import ForeignKey

from pay_api.utils.enums import EFTProcessStatus

from .base_model import BaseModel
from .db import db


class EFTFile(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages the file data for EFT transactions."""

    __tablename__ = "eft_files"
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
        "include_properties": [
            "id",
            "completed_on",
            "created_on",
            "deposit_from_date",
            "deposit_to_date",
            "file_creation_date",
            "file_ref",
            "status_code",
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_on = db.Column(
        "created_on",
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
    )
    completed_on = db.Column("completed_on", db.DateTime, nullable=True)
    deposit_from_date = db.Column("deposit_from_date", db.DateTime, nullable=True)
    deposit_to_date = db.Column("deposit_to_date", db.DateTime, nullable=True)
    file_creation_date = db.Column("file_creation_date", db.DateTime, nullable=True)
    file_ref = db.Column("file_ref", db.String, nullable=False, index=True)
    status_code = db.Column(
        db.String,
        ForeignKey("eft_process_status_codes.code"),
        default=EFTProcessStatus.IN_PROGRESS.value,
        nullable=False,
    )
