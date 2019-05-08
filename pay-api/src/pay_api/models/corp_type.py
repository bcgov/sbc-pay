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
"""Model to handle all operations related to Corp type master data."""

from .db import db, ma


class CorpType(db.Model):
    """This class manages all of the base data about a Corp Type.

    Corp types are different types of corporation the payment system supports
    """

    __tablename__ = 'corp_type'

    corp_type_code = db.Column(db.String(10), primary_key=True)
    corp_type_description = db.Column('corp_type_description', db.String(200), nullable=False)

    @classmethod
    def find_by_corp_type_code(cls, code):
        """Given a corp_type_code, this will return corp type details."""
        corp_type = cls.query.filter_by(corp_type_code=code).one_or_none()
        return corp_type

    def save(self):
        """Save fee code."""
        db.session.add(self)
        db.session.commit()


class CorpTypeSchema(ma.ModelSchema):
    """Main schema used to serialize the Business."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = CorpType
