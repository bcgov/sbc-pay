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
"""Model to handle all operations related to Corp type master data."""

from sqlalchemy import Boolean

from .code_table import CodeTable
from .db import db, ma


class CorpType(db.Model, CodeTable):
    """This class manages all of the base data about a Corp Type.

    Corp types are different types of corporation the payment system supports
    """

    __tablename__ = "corp_types"
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
            "batch_type",
            "bcol_code_full_service_fee",
            "bcol_code_no_service_fee",
            "bcol_code_partial_service_fee",
            "bcol_staff_fee_code",
            "code",
            "description",
            "has_partner_disbursements",
            "is_online_banking_allowed",
            "payment_methods",
            "refund_approval",
            "product",
        ]
    }

    code = db.Column("code", db.String(10), primary_key=True)
    description = db.Column("description", db.String(200), nullable=False)
    bcol_code_full_service_fee = db.Column(db.String(20), nullable=True)
    bcol_code_partial_service_fee = db.Column(db.String(20), nullable=True)
    bcol_code_no_service_fee = db.Column(db.String(20), nullable=True)
    bcol_staff_fee_code = db.Column(db.String(20), nullable=True)
    is_online_banking_allowed = db.Column(Boolean(), default=True)
    has_partner_disbursements = db.Column(Boolean(), default=False)
    batch_type = db.Column(db.String(2), nullable=True)
    product = db.Column(db.String(20), nullable=True)
    payment_methods = db.Column(db.ARRAY(db.String()), nullable=True)
    refund_approval = db.Column(db.Boolean, nullable=False, default=False)

    def save(self):
        """Save corp type."""
        db.session.add(self)
        db.session.commit()

    def __str__(self):
        """Override to string."""
        return f"{self.code}"


class CorpTypeSchema(ma.SQLAlchemyAutoSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Business."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = CorpType
        load_instance = True
