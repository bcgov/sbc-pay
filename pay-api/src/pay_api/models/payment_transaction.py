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
"""Model to handle all operations related to Payment Transaction."""
import uuid
from datetime import datetime, timedelta

from marshmallow import fields
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from pay_api.utils.enums import Status

from .base_model import BaseModel
from .base_schema import BaseSchema
from .db import db, ma


class PaymentTransaction(BaseModel):  # pylint: disable=too-few-public-methods
    """This class manages all of the base data about Payment Transaction."""

    __tablename__ = 'payment_transaction'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status_code = db.Column(db.String(20), ForeignKey('status_code.code'), nullable=False)
    payment_id = db.Column(db.Integer, ForeignKey('payment.id'), nullable=False)
    client_system_url = db.Column(db.String(500), nullable=True)
    pay_system_url = db.Column(db.String(500), nullable=True)

    transaction_start_time = db.Column(db.DateTime, default=datetime.now, nullable=False)
    transaction_end_time = db.Column(db.DateTime, nullable=True)

    @classmethod
    def find_by_payment_id(cls, payment_id: int):
        """Return Payment Transactions by payment identifier."""
        return cls.query.filter_by(payment_id=payment_id).all()

    @classmethod
    def find_active_by_payment_id(cls, payment_id: int):
        """Return Active Payment Transactions by payment identifier."""
        return cls.query.filter_by(payment_id=payment_id).filter_by(status_code=Status.CREATED.value).one_or_none()

    @classmethod
    def find_by_id_and_payment_id(cls, identifier: uuid, payment_id: int):
        """Return Payment Transactions by payment identifier."""
        return cls.query.filter_by(payment_id=payment_id).filter_by(id=identifier).one_or_none()

    @classmethod
    def find_stale_records(cls, days: int = 0, hours: int = 0, minutes: int = 0):
        """Return old records who elapsed a certain time and is not complete.

        Used in the batch job to find orphan records which are untouched for a time.
        """
        oldest_transaction_time = datetime.now() - (timedelta(days=days, hours=hours, minutes=minutes))
        completed_status = [Status.COMPLETED.value, Status.CANCELLED.value, Status.FAILED.value]
        return cls.query.filter(PaymentTransaction.status_code.notin_(completed_status)). \
            filter(PaymentTransaction.transaction_start_time < oldest_transaction_time).all()


class PaymentTransactionSchema(BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the PaymentTransaction."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = PaymentTransaction

    status_code = fields.String(data_key='status_code')
    payment_id = fields.Integer(data_key='payment_id')
    transaction_end_time = fields.String(data_key='end_time')
    transaction_start_time = fields.String(data_key='start_time')

    # pylint: disable=no-member
    _links = ma.Hyperlinks({
        'self': ma.URLFor('API.transactions_transactions', payment_id='<payment_id>', transaction_id='<id>'),
        'collection': ma.URLFor('API.transactions_transaction', payment_id='<payment_id>')
    })
