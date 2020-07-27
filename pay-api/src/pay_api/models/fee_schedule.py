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
"""Model to handle all operations related to fee and fee schedule."""

from datetime import date, datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from .corp_type import CorpType
from .db import db, ma
from .fee_code import FeeCode
from .filing_type import FilingType


class FeeSchedule(db.Model):
    """This class manages all of the base data about a fee schedule.

    Fee schedule holds the data related to filing type and fee code which is used to calculate the fees for a filing
    """

    __tablename__ = 'fee_schedule'
    __table_args__ = (
        db.UniqueConstraint('filing_type_code', 'corp_type_code', 'fee_code', name='unique_fee_sched_1'),
    )

    fee_schedule_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filing_type_code = db.Column(db.String(10), ForeignKey('filing_type.code'), nullable=False)
    corp_type_code = db.Column(db.String(10), ForeignKey('corp_type.code'), nullable=False)
    fee_code = db.Column(db.String(10), ForeignKey('fee_code.code'), nullable=False)
    fee_start_date = db.Column('fee_start_date', db.Date, default=date.today(), nullable=False)
    fee_end_date = db.Column('fee_end_date', db.Date, default=None, nullable=True)
    future_effective_fee_code = db.Column(db.String(10), ForeignKey('fee_code.code'), nullable=True)
    priority_fee_code = db.Column(db.String(10), ForeignKey('fee_code.code'), nullable=True)
    service_fee_code = db.Column(db.String(10), ForeignKey('fee_code.code'), nullable=True)

    filing_type = relationship(FilingType, foreign_keys=[filing_type_code], lazy='joined', innerjoin=True)
    corp_type = relationship(CorpType, foreign_keys=[corp_type_code], lazy='joined', innerjoin=True)
    fee = relationship(FeeCode, foreign_keys=[fee_code], lazy='joined', innerjoin=True)
    future_effective_fee = relationship(FeeCode, foreign_keys=[future_effective_fee_code], lazy='joined',
                                        innerjoin=False)
    priority_fee = relationship(FeeCode, foreign_keys=[priority_fee_code], lazy='joined', innerjoin=False)
    service_fee = relationship(FeeCode, foreign_keys=[service_fee_code], lazy='joined', innerjoin=False)

    # distribution_codes = relationship("DistributionCode", secondary="distribution_code_link")

    @classmethod
    def find_by_filing_type_and_corp_type(cls, corp_type_code: str,
                                          filing_type_code: str,
                                          valid_date: datetime = None
                                          ):
        """Given a filing_type_code and corp_type, this will return fee schedule."""
        if not valid_date:
            valid_date = date.today()
        fee_schedule = None

        if filing_type_code and corp_type_code:
            query = cls.query.filter_by(filing_type_code=filing_type_code). \
                filter_by(corp_type_code=corp_type_code). \
                filter(FeeSchedule.fee_start_date <= valid_date). \
                filter((FeeSchedule.fee_end_date.is_(None)) | (FeeSchedule.fee_end_date >= valid_date))

            fee_schedule = query.one_or_none()

        return fee_schedule

    @classmethod
    def find_all(cls, corp_type_code: str = None, filing_type_code: str = None):
        """Find all fee schedules matching the filters."""
        valid_date = date.today()
        query = cls.query.filter(FeeSchedule.fee_start_date <= valid_date). \
            filter((FeeSchedule.fee_end_date.is_(None)) | (FeeSchedule.fee_end_date >= valid_date))

        if filing_type_code:
            query = query.filter_by(filing_type_code=filing_type_code)

        if corp_type_code:
            query = query.filter_by(corp_type_code=corp_type_code)

        return query.all()

    def save(self):
        """Save fee schedule."""
        db.session.add(self)
        db.session.commit()


class FeeScheduleSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Business."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = FeeSchedule
