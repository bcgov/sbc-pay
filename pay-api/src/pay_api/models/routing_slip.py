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
"""Model to handle all operations related to Routing Slip."""

from sqlalchemy import ForeignKey

from .audit import Audit, AuditSchema
from .db import db, ma


class RoutingSlip(Audit):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Routing Slip."""

    __tablename__ = 'routing_slips'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number = db.Column(db.String(), unique=True)
    payment_account_id = db.Column(db.Integer, ForeignKey('payment_accounts.id'), nullable=True)
    status = db.Column(db.String(), ForeignKey('routing_slip_status_codes.code'), nullable=True)
    total = db.Column(db.Numeric(), nullable=True, default=0)
    remaining_amount = db.Column(db.Numeric(), nullable=True, default=0)
    routing_slip_date = db.Column('routing_slip_date', db.Date, nullable=False)


class RoutingSlipSchema(AuditSchema, ma.ModelSchema):  # pylint: disable=too-many-ancestors, too-few-public-methods
    """Main schema used to serialize the Routing Slip."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = RoutingSlip
