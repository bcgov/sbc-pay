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
"""Model that is populated from feedback files."""
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, func

from .base_model import BaseModel
from .db import db


# NOTE THIS IS SPECIFIC ONLY FOR PAD / ONLINE BANKING CREDIT MEMOS.
# This can also be seen in the ar_applied_receivables table in the CAS datawarehouse.
class CfsCreditInvoices(BaseModel):
    """This class manages the mapping from cfs account credit memos to invoices."""

    __tablename__ = 'cfs_credit_invoices'
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
            'account_id',
            'amount_applied',
            'application_id',
            'cfs_account',
            'cfs_identifier',
            'credit_id',
            'created_on',
            'invoice_account',
            'invoice_number'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    account_id = db.Column(db.Integer, ForeignKey('payment_accounts.id'), nullable=True, index=True)
    amount_applied = db.Column(db.Numeric, nullable=False)
    application_id = db.Column(db.Integer, nullable=False, index=True, unique=True)
    cfs_account = db.Column(db.String(50), nullable=False, index=True)
    cfs_identifier = db.Column(db.String(50), nullable=False, index=True)
    credit_id = db.Column(db.Integer, ForeignKey('credits.id'), nullable=True, index=True)
    created_on = db.Column('created_on', db.DateTime, nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    invoice_amount = db.Column(db.Numeric, nullable=False)
    invoice_number = db.Column(db.String(50), nullable=False)

    @classmethod
    def credit_for_invoice_number(cls, invoice_number: str):
        """Return the credit associated with the invoice number."""
        return cls.query.with_entities(func.sum(CfsCreditInvoices.amount_applied).label('invoice_total')) \
            .filter_by(invoice_number=invoice_number).scalar()
