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
"""Model to handle all operations related to Corp type master data."""

from flask import current_app
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from pay_api.utils.enums import Role
from pay_api.utils.user_context import UserContext, user_context
from .code_table import CodeTable
from .db import db, ma


class CorpType(db.Model, CodeTable):
    """This class manages all of the base data about a Corp Type.

    Corp types are different types of corporation the payment system supports
    """

    __tablename__ = 'corp_type'

    code = db.Column('code', db.String(10), primary_key=True)
    description = db.Column('description', db.String(200), nullable=False)
    service_fee_code = db.Column(db.String(10), ForeignKey('fee_code.code'), nullable=True)
    bcol_fee_code = db.Column(db.String(20), nullable=True)
    bcol_staff_fee_code = db.Column(db.String(20), nullable=True)
    gl_memo = db.Column(db.String(50), nullable=True)
    service_gl_memo = db.Column(db.String(50), nullable=True)

    service_fee = relationship('FeeCode', foreign_keys=[service_fee_code], lazy='joined', innerjoin=False)

    def save(self):
        """Save corp type."""
        db.session.add(self)
        db.session.commit()

    @staticmethod
    @user_context
    def get_service_fees(corp_type_code: str, fee: float, **kwargs):
        """Calculate service_fees fees."""
        current_app.logger.debug(f'<calculate_service_fees - {corp_type_code}')
        user: UserContext = kwargs['user']

        service_fees: float = 0
        # TODO for system accounts with role EXCLUDE_SERVICE_FEES, do not charge service fees for now.
        #  Handle it properly later
        if not user.is_staff() and not (user.is_system() and Role.EXCLUDE_SERVICE_FEES.value in user.roles) and fee > 0:
            corp_type = CorpType.find_by_code(corp_type_code)
            if corp_type.service_fee:
                service_fees = corp_type.service_fee.amount

        return service_fees


class CorpTypeSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Business."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = CorpType
