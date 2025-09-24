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
"""Model to handle all operations related to fee and fee schedule."""

from datetime import UTC, datetime
from decimal import Decimal

from attr import define
from sqlalchemy import Boolean, Date, ForeignKey, cast
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship

from pay_api.utils.serializable import Serializable

from .base_model import BaseModel
from .corp_type import CorpType, CorpTypeSchema
from .db import db, ma
from .fee_code import FeeCode
from .filing_type import FilingType, FilingTypeSchema


class FeeSchedule(BaseModel):
    """This class manages all of the base data about a fee schedule.

    Fee schedule holds the data related to filing type and fee code which is used to calculate the fees for a filing
    """

    __tablename__ = "fee_schedules"
    __table_args__ = (db.UniqueConstraint("filing_type_code", "corp_type_code", "fee_code", name="unique_fee_sched_1"),)
    # this mapper is used so that new and old versions of the service can be run simultaneously,
    # making rolling upgrades easier
    # This is used by SQLAlchemy to explicitly define which fields we're interested
    # so it doesn't freak out and say it can't map the structure if other fields are present.
    # This could occur from a failed deploy or during an upgrade.
    # The other option is to tell SQLAlchemy to ignore differences, but that is ambiguous
    # and can interfere with Alembic upgrades.
    #
    # NOTE: please keep mapper names in alpha-order, easier to track that way
    #       Exception, id is always first, _fields first
    __mapper_args__ = {
        "include_properties": [
            "corp_type_code",
            "gst_added",
            "fee_code",
            "fee_end_date",
            "fee_schedule_id",
            "fee_start_date",
            "filing_type_code",
            "future_effective_fee_code",
            "priority_fee_code",
            "service_fee_code",
            "show_on_pricelist",
            "variable",
        ]
    }

    fee_schedule_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filing_type_code = db.Column(db.String(10), ForeignKey("filing_types.code"), nullable=False)
    corp_type_code = db.Column(db.String(10), ForeignKey("corp_types.code"), nullable=False)
    fee_code = db.Column(db.String(10), ForeignKey("fee_codes.code"), nullable=False)
    fee_start_date = db.Column(
        "fee_start_date",
        db.Date,
        default=lambda: datetime.now(tz=UTC).date(),
        nullable=False,
    )
    fee_end_date = db.Column("fee_end_date", db.Date, default=None, nullable=True)
    future_effective_fee_code = db.Column(db.String(10), ForeignKey("fee_codes.code"), nullable=True)
    priority_fee_code = db.Column(db.String(10), ForeignKey("fee_codes.code"), nullable=True)
    service_fee_code = db.Column(db.String(10), ForeignKey("fee_codes.code"), nullable=True)
    variable = db.Column(Boolean(), default=False, comment="Flag to indicate if the fee is variable")
    show_on_pricelist = db.Column(Boolean(), nullable=False, default=False)
    gst_added = db.Column(Boolean(), default=False, comment="Flag to indicate if GST is added for this fee schedule")

    filing_type = relationship(FilingType, foreign_keys=[filing_type_code], lazy="joined", innerjoin=True)
    corp_type = relationship(CorpType, foreign_keys=[corp_type_code], lazy="joined", innerjoin=True)

    fee = relationship(FeeCode, foreign_keys=[fee_code], lazy="select", innerjoin=True)
    future_effective_fee = relationship(
        FeeCode,
        foreign_keys=[future_effective_fee_code],
        lazy="select",
        innerjoin=False,
    )
    priority_fee = relationship(FeeCode, foreign_keys=[priority_fee_code], lazy="select", innerjoin=False)
    service_fee = relationship(FeeCode, foreign_keys=[service_fee_code], lazy="select", innerjoin=False)

    @declared_attr
    def distribution_codes(cls):  # pylint:disable=no-self-argument, # noqa: N805
        """Distribution code relationship."""
        return relationship(
            "DistributionCode",
            secondary="distribution_code_links",
            backref="fee_schedules",
            lazy="dynamic",
        )

    def __str__(self):
        """Override to string."""
        return f"{self.corp_type_code} - {self.filing_type_code}"

    @classmethod
    def find_by_filing_type_and_corp_type(cls, corp_type_code: str, filing_type_code: str, valid_date: datetime = None):
        """Given a filing_type_code and corp_type, this will return fee schedule."""
        if not valid_date:
            valid_date = datetime.now(tz=UTC).date()
        fee_schedule = None

        if filing_type_code and corp_type_code:
            query = (
                cls.query.filter_by(filing_type_code=filing_type_code)
                .filter_by(corp_type_code=corp_type_code)
                .filter(FeeSchedule.fee_start_date <= cast(valid_date, Date))
                .filter((FeeSchedule.fee_end_date.is_(None)) | (FeeSchedule.fee_end_date >= cast(valid_date, Date)))
            )

            fee_schedule = query.one_or_none()

        return fee_schedule


class FeeScheduleSchema(ma.SQLAlchemyAutoSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Business."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = FeeSchedule
        load_instance = True
        exclude = ["distribution_codes"]

    # pylint: disable=no-member
    corp_type = ma.Nested(
        CorpTypeSchema,
        many=False,
        data_key="corp_type_code",
        exclude=[
            "bcol_code_full_service_fee",
            "bcol_code_partial_service_fee",
            "bcol_code_no_service_fee",
            "bcol_staff_fee_code",
            "batch_type",
        ],
    )
    filing_type = ma.Nested(FilingTypeSchema, many=False, data_key="filing_type_code")


@define
class FeeDetailsSchema(Serializable):
    """Schema for fee details."""

    corp_type: str
    filing_type: str
    corp_type_description: str
    product_code: str
    service: str
    fee: Decimal
    service_charge: Decimal
    gst: Decimal
    fee_gst: Decimal
    service_charge_gst: Decimal
    variable: bool
