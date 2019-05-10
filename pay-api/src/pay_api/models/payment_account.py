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
"""Model to handle all operations related to Payment Status master data."""
from datetime import date, datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from .db import db, ma
from .auditable import Auditable


class PaymentAccount(db.Model, Auditable):
    """This class manages all of the base data about a Payment Status Code.
    """

    __tablename__ = 'payment_account'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    corp_number = db.Column(db.String(20), nullable=False)
    corp_name = db.Column(db.String(150), nullable=False)
    corp_type_code = db.Column(db.String(10), ForeignKey('corp_type.code'), nullable=False)
    payment_system_code = db.Column(db.String(10), ForeignKey('payment_system.code'), nullable=False)
    account_number = db.Column(db.String(50), nullable=True)
    party_number = db.Column(db.String(50), nullable=True)
    site_number = db.Column(db.String(50), nullable=True)

    def save(self):
        """Save status."""
        db.session.add(self)
        db.session.commit()


class PaymentAccountSchema(ma.ModelSchema):
    """Main schema used to serialize the Status Code."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = PaymentAccount
