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

from datetime import datetime

from sqlalchemy import ForeignKey

from pay_api.utils.enums import EjvFileType
from .base_model import BaseModel
from .db import db


class EjvFile(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data about EJV distributions and payment."""

    __tablename__ = 'ejv_files'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_on = db.Column('created_on', db.DateTime, nullable=False, default=datetime.now)
    completed_on = db.Column('completed_on', db.DateTime, nullable=True)
    file_type = db.Column('file_type', db.String, nullable=True, default=EjvFileType.DISBURSEMENT.value)
    file_ref = db.Column('file_ref', db.String, nullable=False, index=True)
    disbursement_status_code = db.Column(db.String(20), ForeignKey('disbursement_status_codes.code'), nullable=True)
    message = db.Column('message', db.String, nullable=True, index=False)
    feedback_file_ref = db.Column('feedback_file_ref', db.String, nullable=True)
