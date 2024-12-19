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
"""Model to handle products and payment methods combo."""

from sqlalchemy.dialects.postgresql import ARRAY

from .base_model import BaseModel
from .db import db


class Product(BaseModel):
    """This class manages the products."""

    __tablename__ = "products"

    product_code = db.Column(db.String, primary_key=True, nullable=False)
    payment_methods = db.Column(ARRAY(db.String), nullable=True)
