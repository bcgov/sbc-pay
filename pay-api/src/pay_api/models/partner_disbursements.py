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
"""Model to track Partner Disbursements, need this table because invoices can be reversed and applied multiple times.

This is used in three different distinct flows for EFT only currently (provided the partner disbursements enabled):

1. Invoice creation - create a Partner Disbursement record
2. Invoice reversal - create a Partner Disbursement reversal record
3. Statement reversal - EFT specific, create a Partner Disbursement reversal record

"""

from datetime import UTC, datetime

from pay_api.utils.enums import DisbursementStatus

from .base_model import BaseModel
from .db import db


class PartnerDisbursements(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages the partner disbursements that should be executed."""

    __tablename__ = "partner_disbursements"
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
            "amount",
            "created_on",
            "feedback_on",
            "is_reversal",
            "partner_code",
            "processed_on",
            "status_code",
            "target_id",
            "target_type",
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    amount = db.Column(db.Numeric, nullable=False)
    created_on = db.Column(
        "created_on",
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(tz=UTC),
    )
    feedback_on = db.Column("feedback_on", db.DateTime, nullable=True)
    partner_code = db.Column("partner_code", db.String(50), nullable=False)
    processed_on = db.Column("processed_on", db.DateTime, nullable=True)
    is_reversal = db.Column("is_reversal", db.Boolean(), nullable=False, default=False)
    status_code = db.Column("status_code", db.String(25), nullable=False)
    target_id = db.Column(db.Integer, nullable=True)
    target_type = db.Column(db.String(50), nullable=True)

    @classmethod
    def find_by_target(cls, target_id: int, target_type: str):
        """Find the Partner Disbursement by target."""
        return cls.query.filter_by(target_id=target_id, target_type=target_type).first()

    @classmethod
    def find_by_target_latest_exclude_cancelled(cls, target_id: int, target_type: str):
        """Find the latest Partner Disbursement by target."""
        return (
            cls.query.filter_by(target_id=target_id, target_type=target_type)
            .filter(PartnerDisbursements.status_code != DisbursementStatus.CANCELLED.value)
            .order_by(PartnerDisbursements.id.desc())
            .first()
        )
