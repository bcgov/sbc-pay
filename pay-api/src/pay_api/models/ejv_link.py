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
"""Model to link invoices with Electronic Journal Voucher."""

from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db


class EjvLink(BaseModel):  # pylint: disable=too-few-public-methods
    """This class manages linkages between EJV and invoices."""

    __tablename__ = 'ejv_links'
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
            'disbursement_status_code',
            'ejv_header_id',
            'link_id',
            'link_type',
            'message',
            'sequence'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    disbursement_status_code = db.Column(db.String(20), ForeignKey('disbursement_status_codes.code'), nullable=True)
    ejv_header_id = db.Column(db.Integer, ForeignKey('ejv_headers.id'), nullable=False, index=True)
    link_id = db.Column(db.Integer, nullable=True, index=True)  # Repurposed for generic linking
    link_type = db.Column(db.String(50), nullable=True, index=True)
    message = db.Column('message', db.String, nullable=True, index=False)
    sequence = db.Column(db.Integer, nullable=True)

    @classmethod
    def find_ejv_link_by_link_id(cls, link_id: str):
        """Return any ejv link by link_id."""
        return cls.query.filter_by(link_id=link_id).first()
