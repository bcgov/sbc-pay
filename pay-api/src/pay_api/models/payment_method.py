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
"""Model to handle all operations related to Payment Method code table."""

from .code_table import CodeTable
from .db import db, ma


class PaymentMethod(db.Model, CodeTable):
    """This class manages all of the base data about Payment Method."""

    __tablename__ = "payment_methods"
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
    __mapper_args__ = {"include_properties": ["code", "description", "partial_refund"]}

    code = db.Column(db.String(15), primary_key=True)
    description = db.Column("description", db.String(200), nullable=False)
    partial_refund = db.Column(db.Boolean, nullable=False, default=False)

    def save(self):
        """Save status."""
        db.session.add(self)
        db.session.commit()

    @classmethod
    def is_payment_method_allowed_for_partial_refund(cls, payment_method_code: str) -> bool:
        """Check if the payment method is allowed for partial refund."""
        payment_method = cls.query.filter_by(code=payment_method_code).first()
        return payment_method.partial_refund if payment_method else False


class PaymentMethodSchema(ma.SQLAlchemyAutoSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the System Code."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = PaymentMethod
        load_instance = True
