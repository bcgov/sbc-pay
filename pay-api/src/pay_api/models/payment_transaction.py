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
"""Model to handle all operations related to Payment Transaction."""
import uuid
from datetime import datetime, timedelta, timezone

import pytz
from marshmallow import fields
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from pay_api.utils.constants import LEGISLATIVE_TIMEZONE
from pay_api.utils.enums import InvoiceReferenceStatus, PaymentMethod, TransactionStatus

from .base_model import BaseModel
from .base_schema import BaseSchema
from .db import db


class PaymentTransaction(BaseModel):  # pylint: disable=too-few-public-methods, too-many-instance-attributes
    """This class manages all of the base data about Payment Transaction."""

    __tablename__ = 'payment_transactions'
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
            'id',
            'status_code',
            'client_system_url',
            'pay_system_url',
            'pay_response_url',
            'pay_system_reason_code',
            'payment_id',
            'transaction_end_time',
            'transaction_start_time'
        ]
    }

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status_code = db.Column(db.String(20), ForeignKey('transaction_status_codes.code'), nullable=False)
    payment_id = db.Column(db.Integer, ForeignKey('payments.id'), nullable=False)
    client_system_url = db.Column(db.String(500), nullable=True)
    pay_system_url = db.Column(db.String(2000), nullable=True)
    pay_response_url = db.Column(db.String(2000), nullable=True)
    pay_system_reason_code = db.Column(db.String(2000), nullable=True)

    transaction_start_time = db.Column(db.DateTime, default=datetime.now(tz=timezone.utc), nullable=False)
    transaction_end_time = db.Column(db.DateTime, nullable=True)

    @classmethod
    def find_by_payment_id(cls, payment_id: int):
        """Return Payment Transactions by payment identifier."""
        return cls.query.filter_by(payment_id=payment_id).all()

    @classmethod
    def find_active_by_payment_id(cls, payment_id: int):
        """Return Active Payment Transactions by payment identifier."""
        return cls.query.filter_by(payment_id=payment_id).filter_by(
            status_code=TransactionStatus.CREATED.value).one_or_none()

    @classmethod
    def find_active_by_invoice_id(cls, invoice_id: int):
        """Return Active Payment Transactions by invoice identifier."""
        # pylint: disable=import-outside-toplevel, cyclic-import
        from .invoice import Invoice
        from .invoice_reference import InvoiceReference
        from .payment import Payment

        query = db.session.query(PaymentTransaction) \
            .join(Payment) \
            .join(InvoiceReference, InvoiceReference.invoice_number == Payment.invoice_number) \
            .join(Invoice, InvoiceReference.invoice_id == Invoice.id) \
            .filter(Invoice.id == invoice_id) \
            .filter(InvoiceReference.status_code == InvoiceReferenceStatus.ACTIVE.value) \
            .filter(PaymentTransaction.status_code == TransactionStatus.CREATED.value)

        return query.one_or_none()

    @classmethod
    def find_recent_completed_by_invoice_id(cls, invoice_id: int):
        """Return Completed Payment Transactions by invoice identifier."""
        # pylint: disable=import-outside-toplevel, cyclic-import
        from .invoice import Invoice
        from .invoice_reference import InvoiceReference
        from .payment import Payment

        query = db.session.query(PaymentTransaction) \
            .join(Payment) \
            .join(InvoiceReference, InvoiceReference.invoice_number == Payment.invoice_number) \
            .join(Invoice, InvoiceReference.invoice_id == Invoice.id) \
            .filter(Invoice.id == invoice_id) \
            .filter(PaymentTransaction.status_code == TransactionStatus.COMPLETED.value) \
            .order_by(PaymentTransaction.transaction_end_time.desc())

        return query.first()

    @classmethod
    def find_by_invoice_id(cls, invoice_id: int):
        """Return all Payment Transactions by invoice identifier."""
        # pylint: disable=import-outside-toplevel, cyclic-import
        from .invoice import Invoice
        from .invoice_reference import InvoiceReference
        from .payment import Payment

        query = db.session.query(PaymentTransaction) \
            .join(Payment) \
            .join(InvoiceReference, InvoiceReference.invoice_number == Payment.invoice_number) \
            .join(Invoice, InvoiceReference.invoice_id == Invoice.id) \
            .filter(Invoice.id == invoice_id)

        return query.all()

    @classmethod
    def find_stale_records(cls, days: int = 0, hours: int = 0, minutes: int = 0):
        """Return old records who elapsed a certain time and is not complete.

        Used in the batch job to find orphan records which are untouched for a time.
        """
        # pylint: disable=import-outside-toplevel, cyclic-import
        from .payment import Payment

        oldest_transaction_time = datetime.now(tz=timezone.utc) - (timedelta(days=days, hours=hours, minutes=minutes))
        completed_status = [TransactionStatus.COMPLETED.value, TransactionStatus.CANCELLED.value,
                            TransactionStatus.FAILED.value]
        return db.session.query(PaymentTransaction)\
            .join(Payment, Payment.id == PaymentTransaction.payment_id)\
            .filter(PaymentTransaction.status_code.notin_(completed_status))\
            .filter(PaymentTransaction.transaction_start_time < oldest_transaction_time) \
            .filter(Payment.payment_method_code.in_([PaymentMethod.CC.value, PaymentMethod.DIRECT_PAY.value])) \
            .all()


class PaymentTransactionSchema(BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the PaymentTransaction."""

    class Meta(BaseSchema.Meta):  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = PaymentTransaction

    status_code = fields.String(data_key='status_code')
    payment_id = fields.Integer(data_key='payment_id')
    transaction_end_time = fields.DateTime(tzinfo=pytz.timezone(LEGISLATIVE_TIMEZONE),
                                           data_key='end_time')
    transaction_start_time = fields.DateTime(tzinfo=pytz.timezone(LEGISLATIVE_TIMEZONE),
                                             data_key='start_time')
