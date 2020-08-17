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
"""Model to handle statement to Invoice relation data.

For one statement , there could be a lot of invoices.
"""

from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db, ma


class StatementInovices(BaseModel):
    """This class manages the statements related data."""

    __tablename__ = 'statement_invoices'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    statement_id = db.Column(db.Integer, ForeignKey('statement.id'), nullable=False, index=True)
    inovice_id = db.Column(db.Integer, ForeignKey('invoice.id'), nullable=False)
    status = db.Column(db.String(50), nullable=True, index=True)


class StatementInovicesSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Statements."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = StatementInovices
