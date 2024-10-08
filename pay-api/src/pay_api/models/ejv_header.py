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
"""Model to handle Electronic Journal Voucher distributions and payment."""

from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db


class EjvHeader(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about EJV Header."""

    __tablename__ = "ejv_headers"
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
            "disbursement_status_code",
            "ejv_file_id",
            "partner_code",
            "payment_account_id",
            "message",
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    disbursement_status_code = db.Column(db.String(20), ForeignKey("disbursement_status_codes.code"), nullable=True)
    ejv_file_id = db.Column(db.Integer, ForeignKey("ejv_files.id"), nullable=False)
    partner_code = db.Column(db.String(10), ForeignKey("corp_types.code"), nullable=True)  # For partners
    payment_account_id = db.Column(db.Integer, ForeignKey("payment_accounts.id"), nullable=True)  # For gov accounts
    message = db.Column("message", db.String, nullable=True, index=False)
