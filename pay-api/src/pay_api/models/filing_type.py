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
"""Model to handle all operations related to filing type master data."""

from .code_table import CodeTable
from .db import db, ma


class FilingType(db.Model, CodeTable):
    """This class manages all of the base data about a filing type.

    Filing type indicates the filing operation on the entity
    """

    __tablename__ = 'filing_types'

    code = db.Column(db.String(10), primary_key=True)
    description = db.Column('description', db.String(200), nullable=False)

    def save(self):
        """Save filing type."""
        db.session.add(self)
        db.session.commit()

    def __str__(self):
        """Override to string."""
        return f'{self.code}'


class FilingTypeSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Business."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = FilingType
