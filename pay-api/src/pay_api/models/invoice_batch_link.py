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
"""Model to link invoices with nightly transactions roll up."""

from sqlalchemy import ForeignKey

from .base_model import BaseModel
from .db import db


class InvoiceBatchLink(BaseModel):  # pylint: disable=too-few-public-methods
    """This class manages linkages between invoices and nightly roll up."""

    __tablename__ = 'invoice_batch_links'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.Integer, ForeignKey('invoices.id'), nullable=False)
    batch_id = db.Column(db.Integer, ForeignKey('invoice_batches.id'), nullable=False)
