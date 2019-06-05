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
"""Model to handle all operations related to Payment data."""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from .audit import Audit
from .base_model import BaseModel
from .db import db, ma
from .payment_system import PaymentSystem


class Payment(db.Model, Audit, BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Payment ."""

    __tablename__ = 'payment'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_system_code = db.Column(db.String(10), ForeignKey('payment_system.code'), nullable=False)
    payment_method_code = db.Column(db.String(10), ForeignKey('payment_method.code'), nullable=False)
    payment_status_code = db.Column(db.String(10), ForeignKey('status_code.code'), nullable=False)

    payment_system = relationship(PaymentSystem, foreign_keys=[payment_system_code], lazy='joined', innerjoin=True)

    @classmethod
    def find_by_id(cls, identifier: int):
        """Return a Payment by id."""
        return cls.query.get(identifier)


class PaymentSchema(ma.ModelSchema):
    """Main schema used to serialize the Payment."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Payment
