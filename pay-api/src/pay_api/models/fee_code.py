# Copyright © 2019 Province of British Columbia
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
"""Model to handle all operations related to Fee Code master data."""

from marshmallow import fields

from .code_table import CodeTable
from .db import db, ma


class FeeCode(db.Model, CodeTable):
    """This class manages all of the base data about a Fee Code.

    Fee Codes holds the fee amount
    """

    __tablename__ = 'fee_codes'
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
            'amount',
            'code'
        ]
    }

    code = db.Column(db.String(10), primary_key=True)
    amount = db.Column('amount', db.Numeric(19, 2), nullable=False)

    def save(self):
        """Save fee code."""
        db.session.add(self)
        db.session.commit()

    def __str__(self):
        """Override to string."""
        return f'{self.amount} ({self.code})'


class FeeCodeSchema(ma.SQLAlchemyAutoSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Business."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = FeeCode
        load_instance = True
    amount = fields.Float(data_key='amount')
