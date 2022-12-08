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
"""Model to handle all operations related to Error Code master data."""
from marshmallow import fields

from .code_table import CodeTable
from .db import db, ma


class ErrorCode(db.Model, CodeTable):
    """This class manages all of the base data about a Error Code.

    Error Codes holds the error details produced by the API.
    """

    __tablename__ = 'error_codes'

    code = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(100))
    detail = db.Column(db.String(500))


class ErrorCodeSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Error code."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = ErrorCode

    code = fields.String(data_key='type')
