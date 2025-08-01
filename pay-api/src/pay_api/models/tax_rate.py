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
"""Model to handle all operations related to Tax Rate data."""

from datetime import datetime, timezone

from sql_versioning import Versioned
from sqlalchemy import DateTime, and_

from pay_api.models.base_model import BaseModel
from pay_api.utils.constants import TAX_CLASSIFICATION_GST

from .db import db


class TaxRate(Versioned, BaseModel):
    """This class manages all tax rate related data."""

    __tablename__ = "tax_rates"
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
            "description",
            "effective_end_date",
            "rate",
            "start_date",
            "tax_type",
            "updated_by",
            "updated_name",
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tax_type = db.Column(db.String(10), nullable=False, comment="Tax type such as 'gst', 'pst'")
    rate = db.Column(db.Numeric(6, 4), nullable=False, comment="Tax rate as decimal, e.g. 0.0500 for 5%")
    start_date = db.Column(DateTime(timezone=True), nullable=False, comment="When this tax rate becomes effective")
    effective_end_date = db.Column(DateTime(timezone=True), nullable=True, comment="When this tax rate expires")
    description = db.Column(db.String(200), nullable=True, comment="Description of the tax rate")
    updated_by = db.Column(db.String(50), nullable=False)
    updated_name = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        """Return a string representation of the object."""
        return f"<TaxRate id={self.id} tax_type={self.tax_type} rate={self.rate}>"

    def __str__(self):
        """Return a string representation for display."""
        return f"{self.tax_type}: {self.rate}"

    @classmethod
    def get_current_gst_rate(cls):
        """Get the current effective tax rate for a given tax type (e.g., 'gst', 'pst')."""
        now = datetime.now(tz=timezone.utc)
        return (
            cls.query.filter(
                and_(
                    cls.tax_type == TAX_CLASSIFICATION_GST,
                    cls.start_date <= now,
                    cls.effective_end_date.is_(None) | (cls.effective_end_date > now),
                )
            )
            .order_by(cls.start_date.desc())
            .one()
            .rate
        )
