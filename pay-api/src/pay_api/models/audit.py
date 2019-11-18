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
"""Base class for audit model."""
from flask import current_app
from sqlalchemy.orm import validates

from .db import db


class Audit:  # pylint: disable=too-few-public-methods
    """This class provides base methods for Auditable Table."""

    created_by = db.Column('created_by', db.String(50), nullable=False)
    created_on = db.Column('created_on', db.DateTime, nullable=False)
    updated_by = db.Column('updated_by', db.String(50), nullable=True)
    updated_on = db.Column('updated_on', db.DateTime, nullable=True)

    @validates('created_by', 'updated_by')
    def convert_upper(self, key, value):  # pylint: disable=no-self-use
        """Convert the annotated columns to upper case on save."""
        current_app.logger.debug(f'Converting to upper for Key {key} and value {value}')

        return value.upper() if value else value
