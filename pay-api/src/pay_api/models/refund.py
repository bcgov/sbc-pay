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
"""Model to handle all operations related to invoice refund."""

from sqlalchemy import ForeignKey
from sqlalchemy.schema import CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB

from .base_model import BaseModel
from .db import db, ma


class Refund(BaseModel):
    """This class manages all of the base data about Refunds."""

    __tablename__ = "refunds"

    __table_args__ = (
        CheckConstraint(
            "NOT(routing_slip_id IS NULL AND invoice_id IS NULL)",
            name="routing_slip_invoice" "_id_check",
        ),
    )
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
            "decision_date",
            "decision_made_by",
            "details",
            "gl_posted",
            "gl_error",
            "invoice_id",
            "reason",
            "requested_by",
            "requested_date",
            "routing_slip_id",
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, ForeignKey("invoices.id"), nullable=True)
    routing_slip_id = db.Column(
        db.Integer, ForeignKey("routing_slips.id"), nullable=True
    )
    requested_date = db.Column(db.DateTime)
    reason = db.Column(db.String(250))
    requested_by = db.Column(db.String(50))
    decision_made_by = db.Column(db.String(50))
    decision_date = db.Column(db.DateTime)
    details = db.Column(JSONB)
    # These two fields below are used for direct pay credit card refunds.
    gl_posted = db.Column(db.DateTime, nullable=True)
    gl_error = db.Column(db.String(250), nullable=True)

    @classmethod
    def find_by_invoice_id(cls, invoice_id: int):
        """Return a refund by invoice id."""
        return cls.query.filter_by(invoice_id=invoice_id).one_or_none()

    @classmethod
    def find_by_routing_slip_id(cls, routing_slip_id: int):
        """Return a refund by invoice id."""
        return cls.query.filter_by(routing_slip_id=routing_slip_id).one_or_none()


class RefundSchema(ma.SQLAlchemyAutoSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Refund."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Refund
        load_instance = True
