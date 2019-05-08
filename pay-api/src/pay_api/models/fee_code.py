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

from .db import db, ma


class FeeCode(db.Model):
    """This class manages all of the base data about a Fee Code.

    Fee Codes holds the fee amount
    """

    __tablename__ = 'fee_code'

    fee_code = db.Column(db.String(10), primary_key=True)
    amount = db.Column('amount', db.Integer, nullable=False)

    @classmethod
    def find_by_fee_code(cls, code):
        """Given a fee_code, this will return fee code details."""
        fee_code = cls.query.filter_by(fee_code=code).one_or_none()
        return fee_code

    def save(self):
        """Save fee code."""
        db.session.add(self)
        db.session.commit()


class FeeCodeSchema(ma.ModelSchema):
    """Main schema used to serialize the Business."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = FeeCode
