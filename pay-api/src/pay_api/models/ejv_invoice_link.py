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
"""Model to link invoices with Electronic Journal Voucher."""

from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db


class EjvInvoiceLink(BaseModel):  # pylint: disable=too-few-public-methods
    """This class manages linkages between EJV and invoices."""

    __tablename__ = 'ejv_invoice_links'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, ForeignKey('invoices.id'), nullable=False)
    ejv_header_id = db.Column(db.Integer, ForeignKey('ejv_headers.id'), nullable=False)
    disbursement_status_code = db.Column(db.String(20), ForeignKey('disbursement_status_codes.code'), nullable=True)
    message = db.Column('message', db.String, nullable=True, index=False)
