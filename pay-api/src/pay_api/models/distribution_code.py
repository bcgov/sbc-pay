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
"""Model to handle all operations related to distribution code."""
from __future__ import annotations

from datetime import datetime, timezone

from marshmallow import fields
from sql_versioning import Versioned
from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import relationship

from .audit import Audit, AuditSchema, BaseModel
from .base_schema import BaseSchema
from .db import db, ma


class DistributionCodeLink(BaseModel):
    """This class manages all of the base data about distribution code.

    Distribution code holds details on the codes for how the collected payment is going to be distributed.
    """

    __tablename__ = 'distribution_code_links'
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
        'include_properties': [
            'distribution_code_id',
            'distribution_link_id',
            'fee_schedule_id'
        ]
    }

    distribution_link_id = db.Column(db.Integer, primary_key=True)
    fee_schedule_id = db.Column(db.Integer, ForeignKey('fee_schedules.fee_schedule_id'))
    distribution_code_id = db.Column(db.Integer, ForeignKey('distribution_codes.distribution_code_id'))

    @classmethod
    def find_fee_schedules_by_distribution_id(cls, distribution_code_id: int):
        """Find all distribution codes."""
        from .fee_schedule import FeeSchedule  # pylint: disable=import-outside-toplevel

        query = db.session.query(FeeSchedule). \
            join(DistributionCodeLink, DistributionCodeLink.fee_schedule_id == FeeSchedule.fee_schedule_id). \
            filter(DistributionCodeLink.distribution_code_id == distribution_code_id)
        return query.all()

    @classmethod
    def bulk_save_links(cls, links: list):
        """Bulk save DistributionCodeLink."""
        db.session.bulk_save_objects(links)
        BaseModel.commit()


class DistributionCode(Audit, Versioned, BaseModel):  # pylint:disable=too-many-instance-attributes
    """This class manages all of the base data about distribution code.

    Distribution code holds details on the codes for how the collected payment is going to be distributed.
    """

    __tablename__ = 'distribution_codes'

    distribution_code_id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    name = db.Column(db.String(250), nullable=True)
    client = db.Column(db.String(50), nullable=True)
    responsibility_centre = db.Column(db.String(50), nullable=True)
    service_line = db.Column(db.String(50), nullable=True)
    stob = db.Column(db.String(50), nullable=True)
    project_code = db.Column(db.String(50), nullable=True)

    start_date = db.Column(db.Date, default=datetime.now(tz=timezone.utc).date(), nullable=False)
    end_date = db.Column(db.Date, default=None, nullable=True)
    stop_ejv = db.Column('stop_ejv', Boolean(), default=False)

    service_fee_distribution_code_id = db.Column(db.Integer, ForeignKey('distribution_codes.distribution_code_id'),
                                                 nullable=True)
    disbursement_distribution_code_id = db.Column(db.Integer, ForeignKey('distribution_codes.distribution_code_id'),
                                                  nullable=True)
    # account id for distribution codes for gov account. None for distribution codes for filing types
    account_id = db.Column(db.Integer, ForeignKey('payment_accounts.id'), nullable=True, index=True)

    service_fee_distribution_code = relationship('DistributionCode', foreign_keys=[service_fee_distribution_code_id],
                                                 remote_side=[distribution_code_id], lazy='select')
    disbursement_distribution_code = relationship('DistributionCode', foreign_keys=[disbursement_distribution_code_id],
                                                  remote_side=[distribution_code_id], lazy='select')
    account = relationship('PaymentAccount', lazy='joined')

    def __str__(self):
        """Override to string."""
        return f'{self.name} ({self.client}.{self.responsibility_centre}.{self.service_line}.' \
               f'{self.stob}.{self.project_code})'

    @classmethod
    def find_all(cls, include_gov_account_gl_codes: bool = False):
        """Find all distribution codes."""
        valid_date = datetime.now(tz=timezone.utc).date()
        query = cls.query.filter(DistributionCode.start_date <= valid_date). \
            filter((DistributionCode.end_date.is_(None)) | (DistributionCode.end_date >= valid_date)). \
            order_by(DistributionCode.name.asc())

        query = query.filter(DistributionCode.account_id.isnot(None)) if include_gov_account_gl_codes \
            else query.filter(DistributionCode.account_id.is_(None))

        return query.all()

    @classmethod
    def find_by_service_fee_distribution_id(cls, service_fee_distribution_code_id):
        """Find by service fee distribution id."""
        return cls.query.filter(
            DistributionCode.service_fee_distribution_code_id == service_fee_distribution_code_id).all()

    @classmethod
    def find_by_active_for_fee_schedule(cls, fee_schedule_id: int):
        """Return active distribution for fee schedule."""
        valid_date = datetime.now(tz=timezone.utc).date()
        query = db.session.query(DistributionCode). \
            join(DistributionCodeLink). \
            filter(DistributionCodeLink.fee_schedule_id == fee_schedule_id). \
            filter(DistributionCode.start_date <= valid_date). \
            filter((DistributionCode.end_date.is_(None)) | (DistributionCode.end_date >= valid_date))

        distribution_code = query.one_or_none()
        return distribution_code

    @classmethod
    def find_by_active_for_account(cls, account_id: int):
        """Return active distribution for account."""
        valid_date = datetime.now(tz=timezone.utc).date()
        query = db.session.query(DistributionCode). \
            filter(DistributionCode.account_id == account_id). \
            filter(DistributionCode.start_date <= valid_date). \
            filter((DistributionCode.end_date.is_(None)) | (DistributionCode.end_date >= valid_date))

        distribution_code = query.one_or_none()
        return distribution_code


class DistributionCodeLinkSchema(ma.SQLAlchemyAutoSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the DistributionCodeLink."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = DistributionCodeLink
        exclude = ['disbursement']
        load_instance = True


class DistributionCodeSchema(AuditSchema, BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the DistributionCode."""

    class Meta:  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = DistributionCode

    service_fee_distribution_code_id = fields.String(data_key='service_fee_distribution_code_id')
    disbursement_distribution_code_id = fields.String(data_key='disbursement_distribution_code_id')
    account_id = fields.String(data_key='account_id')
