# Copyright © 2022 Province of British Columbia
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
"""Model to handle nightly roll up batch."""

from datetime import datetime

from .base_model import BaseModel
from .db import db


class InvoiceBatch(BaseModel):  # pylint: disable=too-many-instance-attributes
    """This class manages all of the base data nightly transactions roll up."""

    __tablename__ = 'invoice_batches'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_on = db.Column('created_on', db.DateTime, nullable=False, default=datetime.now)
