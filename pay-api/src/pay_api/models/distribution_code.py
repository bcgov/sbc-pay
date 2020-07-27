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
"""Model to handle all operations related to distribution code."""

from datetime import date

from sqlalchemy import ForeignKey

from .audit import Audit, BaseModel
from .db import db, ma
from .fee_schedule import FeeSchedule


class DistributionCodeLink(BaseModel):
    """This class manages all of the base data about distribution code.

    Distribution code holds details on the codes for how the collected payment is going to be distributed.
    """

    __tablename__ = 'distribution_code_link'

    distribution_link_id = db.Column(db.Integer, primary_key=True)
    fee_schedule_id = db.Column(db.Integer, ForeignKey('fee_schedule.fee_schedule_id'))
    distribution_code_id = db.Column(db.Integer, ForeignKey('distribution_code.distribution_code_id'))

    @classmethod
    def find_fee_schedules_by_distribution_id(cls, distribution_code_id: int):
        """Find all distribution codes."""
        query = db.session.query(FeeSchedule). \
            join(DistributionCodeLink, DistributionCodeLink.fee_schedule_id == FeeSchedule.fee_schedule_id). \
            filter(DistributionCodeLink.distribution_code_id == distribution_code_id)
        return query.all()

    @classmethod
    def bulk_save_links(cls, links: list):
        """Find all distribution codes."""
        db.session.bulk_save_objects(links)
        BaseModel.commit()


class DistributionCode(Audit):  # pylint:disable=too-many-instance-attributes
    """This class manages all of the base data about distribution code.

    Distribution code holds details on the codes for how the collected payment is going to be distributed.
    """

    __tablename__ = 'distribution_code'

    distribution_code_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    memo_name = db.Column(db.String(50), nullable=True)
    service_fee_memo_name = db.Column(db.String(50), nullable=True)

    client = db.Column(db.String(50), nullable=True)
    responsibility_centre = db.Column(db.String(50), nullable=True)
    service_line = db.Column(db.String(50), nullable=True)
    stob = db.Column(db.String(50), nullable=True)
    project_code = db.Column(db.String(50), nullable=True)

    service_fee_client = db.Column(db.String(50), nullable=True)
    service_fee_responsibility_centre = db.Column(db.String(50), nullable=True)
    service_fee_line = db.Column(db.String(50), nullable=True)
    service_fee_stob = db.Column(db.String(50), nullable=True)
    service_fee_project_code = db.Column(db.String(50), nullable=True)

    start_date = db.Column(db.Date, default=date.today(), nullable=False)
    end_date = db.Column(db.Date, default=None, nullable=True)

    @classmethod
    def find_all(cls):
        """Find all distribution codes."""
        valid_date = date.today()
        query = cls.query.filter(DistributionCode.start_date <= valid_date). \
            filter((DistributionCode.end_date.is_(None)) | (DistributionCode.end_date >= valid_date))

        return query.all()

    @classmethod
    def find_by_id(cls, identifier: int):
        """Return by id."""
        return cls.query.get(identifier)

    @classmethod
    def find_by_active_for_fee_schedule(cls, fee_schedule_id: int):
        """Return by id."""
        valid_date = date.today()
        query = db.session.query(DistributionCode). \
            join(DistributionCodeLink). \
            filter(DistributionCodeLink.fee_schedule_id == fee_schedule_id). \
            filter(DistributionCode.start_date <= valid_date). \
            filter((DistributionCode.end_date.is_(None)) | (DistributionCode.end_date >= valid_date))

        distribution_codes = query.all()
        if len(distribution_codes) != 1:
            raise Exception()
        return distribution_codes[0]


class DistributionCodeLinkSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the DistributionCodeLink."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = DistributionCodeLink


class DistributionCodeSchema(ma.ModelSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the DistributionCode."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = DistributionCode
