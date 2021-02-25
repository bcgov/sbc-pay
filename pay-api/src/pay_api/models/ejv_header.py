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
"""Model to handle Electronic Journal Voucher distributions and payment."""

from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db


class EjvHeader(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about EJV Header."""

    __tablename__ = 'ejv_headers'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    disbursement_status_code = db.Column(db.String(20), ForeignKey('disbursement_status_codes.code'), nullable=True)
    ejv_file_id = db.Column(db.Integer, ForeignKey('ejv_files.id'), nullable=False)
    partner_code = db.Column(db.String(10), ForeignKey('corp_types.code'), nullable=True)  # For partners
    payment_account_id = db.Column(db.Integer, ForeignKey('payment_accounts.id'), nullable=True)  # For gov accounts
    message = db.Column('message', db.String, nullable=True, index=False)
