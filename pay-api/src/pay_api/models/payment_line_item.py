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
"""Model to handle all operations related to Payment Line Item."""

from decimal import Decimal
from attrs import define
from marshmallow import fields
from sqlalchemy import ForeignKey, func, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.orm import relationship

from .base_model import BaseModel
from .db import db, ma
from .fee_schedule import FeeSchedule


class PaymentLineItem(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about Payment Line Item."""

    __tablename__ = 'payment_line_items'
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
            'description',
            'fee_distribution_id',
            'fee_schedule_id',
            'filing_fees',
            'future_effective_fees',
            'gst',
            'invoice_id',
            'line_item_status_code',
            'priority_fees',
            'pst',
            'quantity',
            'service_fees',
            'total',
            'waived_fees',
            'waived_by'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, ForeignKey('invoices.id'), nullable=False, index=True)
    filing_fees = db.Column(db.Numeric(19, 2), nullable=False)
    fee_schedule_id = db.Column(db.Integer, ForeignKey('fee_schedules.fee_schedule_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=True)
    priority_fees = db.Column(db.Numeric(19, 2), nullable=True)
    future_effective_fees = db.Column(db.Numeric(19, 2), nullable=True)
    description = db.Column(db.String(200), nullable=True)
    gst = db.Column(db.Numeric(19, 2), nullable=True)
    pst = db.Column(db.Numeric(19, 2), nullable=True)
    total = db.Column(db.Numeric(19, 2), nullable=False)
    line_item_status_code = db.Column(db.String(20), ForeignKey('line_item_status_codes.code'), nullable=False)
    waived_fees = db.Column(db.Numeric(19, 2), nullable=True)
    waived_by = db.Column(db.String(50), nullable=True, default=None)
    service_fees = db.Column(db.Numeric(19, 2), nullable=True)

    fee_distribution_id = db.Column(db.Integer, ForeignKey('distribution_codes.distribution_code_id'), nullable=True)

    fee_schedule = relationship(FeeSchedule, foreign_keys=[fee_schedule_id], lazy='joined', innerjoin=True)

    @classmethod
    def find_by_invoice_ids(cls, invoice_ids: list):
        """Return list of line items by list of invoice ids."""
        invoice_ids = select(func.unnest(array(invoice_ids)))
        return db.session.query(PaymentLineItem).filter(PaymentLineItem.invoice_id.in_(
                invoice_ids)) \
            .order_by(PaymentLineItem.invoice_id.desc()).all()


class PaymentLineItemSchema(ma.SQLAlchemyAutoSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Payment line item."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = PaymentLineItem
        exclude = ['fee_schedule_id', 'fee_schedule']
        load_instance = True

    line_item_status_code = fields.String(data_key='status_code')
    filing_fees = fields.Float(data_key='filing_fees')
    priority_fees = fields.Float(data_key='priority_fees')
    future_effective_fees = fields.Float(data_key='future_effective_fees')
    gst = fields.Float(data_key='gst')
    pst = fields.Float(data_key='pst')
    total = fields.Float(data_key='total')
    waived_fees = fields.Float(data_key='waived_fees')
    service_fees = fields.Float(data_key='service_fees')


@define
class PaymentLineItemSearchModel:  # pylint: disable=too-few-public-methods
    """Payment Line Item Search Model."""

    total: Decimal
    gst: Decimal
    pst: Decimal
    service_fees: Decimal
    description: str
    filing_type_code: str

    @classmethod
    def from_row(cls, row: PaymentLineItem):
        """From row is used so we don't tightly couple to our database class.

        https://www.attrs.org/en/stable/init.html
        """
        return cls(total=row.total, gst=row.gst, pst=row.pst, service_fees=row.service_fees,
                   description=row.description, filing_type_code=row.fee_schedule.filing_type_code)
