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
from operator import or_

from sqlalchemy import Boolean, ForeignKey, func
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship

from .corp_type import CorpType, CorpTypeSchema
from .db import db, ma
from .fee_code import FeeCode
from .filing_type import FilingType, FilingTypeSchema


class FeeSchedule(db.Model):
    """This class manages all of the base data about a fee schedule.

    Fee schedule holds the data related to filing type and fee code which is used to calculate the fees for a filing
    """

    __tablename__ = 'fee_schedules'
    __table_args__ = (
        db.UniqueConstraint('filing_type_code', 'corp_type_code', 'fee_code', name='unique_fee_sched_1'),
    )

    fee_schedule_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filing_type_code = db.Column(db.String(10), ForeignKey('filing_types.code'), nullable=False)
    corp_type_code = db.Column(db.String(10), ForeignKey('corp_types.code'), nullable=False)
    fee_code = db.Column(db.String(10), ForeignKey('fee_codes.code'), nullable=False)
    fee_start_date = db.Column('fee_start_date', db.Date, default=date.today(), nullable=False)
    fee_end_date = db.Column('fee_end_date', db.Date, default=None, nullable=True)
    future_effective_fee_code = db.Column(db.String(10), ForeignKey('fee_codes.code'), nullable=True)
    priority_fee_code = db.Column(db.String(10), ForeignKey('fee_codes.code'), nullable=True)
    service_fee_code = db.Column(db.String(10), ForeignKey('fee_codes.code'), nullable=True)
    variable = db.Column(Boolean(), default=False, comment='Flag to indicate if the fee is variable')

    filing_type = relationship(FilingType, foreign_keys=[filing_type_code], lazy='joined', innerjoin=True)
    corp_type = relationship(CorpType, foreign_keys=[corp_type_code], lazy='joined', innerjoin=True)

    fee = relationship(FeeCode, foreign_keys=[fee_code], lazy='select', innerjoin=True)
    future_effective_fee = relationship(FeeCode, foreign_keys=[future_effective_fee_code], lazy='select',
                                        innerjoin=False)
    priority_fee = relationship(FeeCode, foreign_keys=[priority_fee_code], lazy='select', innerjoin=False)
    service_fee = relationship(FeeCode, foreign_keys=[service_fee_code], lazy='select', innerjoin=False)

    @declared_attr
    def distribution_codes(cls):  # pylint:disable=no-self-argument, # noqa: N805
        """Distribution code relationship."""
        return relationship('DistributionCode', secondary='distribution_code_links', backref='fee_schedules',
                            lazy='dynamic')

    def __str__(self):
        """Override to string."""
        return f'{self.corp_type_code} - {self.filing_type_code}'

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
    def find_by_id(cls, fee_schedule_id: int):
        """Find and return fee schedule by id."""
        return cls.query.get(fee_schedule_id)

    @classmethod
    def find_all(cls, corp_type_code: str = None, filing_type_code: str = None, description: str = None):
        """Find all fee schedules matching the filters."""
        valid_date = date.today()
        query = cls.query.filter(FeeSchedule.fee_start_date <= valid_date). \
            filter((FeeSchedule.fee_end_date.is_(None)) | (FeeSchedule.fee_end_date >= valid_date))

        if filing_type_code:
            query = query.filter_by(filing_type_code=filing_type_code)

        if corp_type_code:
            query = query.filter_by(corp_type_code=corp_type_code)

        if description:
            # TODO arrive at a better search
            descriptions = description.replace(' ', '%')
            query = query.join(CorpType,
                               CorpType.code == FeeSchedule.corp_type_code). \
                join(FilingType, FilingType.code == FeeSchedule.filing_type_code)
            query = query.filter(
                or_(func.lower(FilingType.description).contains(descriptions.lower()),
                    func.lower(CorpType.description).contains(descriptions.lower())))

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

    # pylint: disable=no-member
    corp_type = ma.Nested(CorpTypeSchema, many=False, data_key='corp_type_code',
                          exclude=['bcol_fee_code', 'bcol_staff_fee_code', 'batch_type'])
    filing_type = ma.Nested(FilingTypeSchema, many=False, data_key='filing_type_code')
