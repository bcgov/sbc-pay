# Copyright © 2023 Province of British Columbia
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
"""Model to link invoices with EFT Credits."""
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, text

from .base_model import BaseModel
from .db import db
from ..utils.enums import EFTCreditInvoiceStatus


class EFTCreditInvoiceLink(BaseModel):  # pylint: disable=too-few-public-methods
    """This class manages linkages between EFT Credits and invoices."""

    __tablename__ = 'eft_credit_invoice_links'
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
            'amount',
            'created_on',
            'eft_credit_id',
            'invoice_id',
            'link_group_id',
            'receipt_number',
            'status_code'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, ForeignKey('invoices.id'), nullable=False, index=True)
    eft_credit_id = db.Column(db.Integer, ForeignKey('eft_credits.id'), nullable=False, index=True)
    amount = db.Column(db.Numeric(19, 2), nullable=True)
    status_code = db.Column('status_code', db.String(25), nullable=False, index=True)
    created_on = db.Column('created_on', db.DateTime, nullable=False, default=datetime.now(tz=timezone.utc))
    receipt_number = db.Column(db.String(50), nullable=True)
    link_group_id = db.Column(db.Integer, nullable=True)

    @classmethod
    def find_pending_invoice_links(cls, invoice_id: int):
        """Find active link by short name and account."""
        return (cls.query
                .filter_by(invoice_id=invoice_id)
                .filter(cls.status_code.in_([EFTCreditInvoiceStatus.PENDING.value]))
                ).one_or_none()

    @classmethod
    def get_next_group_link_seq(cls):
        """Get next value of EFT Group Link Sequence."""
        return db.session.execute(text("SELECT nextval('eft_group_link_seq')")).scalar()
