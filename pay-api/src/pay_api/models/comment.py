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
"""Model to handle all operations related to Routing Slip Comment data."""
from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from sqlalchemy.ext.declarative import declared_attr
from marshmallow import fields
from pay_api.utils.user_context import user_context
from .base_model import BaseModel
from .base_schema import BaseSchema
from .db import db
from .routing_slip import RoutingSlip


class Comment(BaseModel):
    """This class manages all of the base data about a Routing Slip Comment.

    Comments holds the comment
    """

    __tablename__ = 'comments'
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
            'id',
            'comment',
            'routing_slip_number',
            'submitter_name',
            'timestamp'
        ]
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    comment = db.Column(db.String(4096))
    timestamp = db.Column('timestamp', db.DateTime(timezone=True), default=lambda: datetime.now(tz=timezone.utc))
    # Parent relationship
    routing_slip_number = db.Column(db.String(), ForeignKey('routing_slips.number'), index=True)
    routing_slip = relationship(RoutingSlip, foreign_keys=[routing_slip_number], lazy='select', innerjoin=True)

    @declared_attr
    def submitter_name(self):  # pylint:disable=no-self-argument, # noqa: N805
        """Return created by."""
        return db.Column('submitter_name', db.String(50), nullable=False, default=self._get_user_name)

    @staticmethod
    @user_context
    def _get_user_name(**kwargs):
        """Return current user user_name."""
        return kwargs['user'].user_name

    @classmethod
    def find_all_comments_for_a_routingslip(cls, routing_slip_number: str):
        """Find all comments specific to a routing slip."""
        query = db.session.query(Comment)\
            .filter(Comment.routing_slip_number == routing_slip_number)\
            .order_by(
            Comment.timestamp.desc())
        return query.all()


class CommentSchema(BaseSchema):  # pylint: disable=too-many-ancestors
    """Main schema used to serialize the Comment."""

    class Meta(BaseSchema.Meta):  # pylint: disable=too-few-public-methods
        """Returns all the fields from the SQLAlchemy class."""

        model = Comment
        exclude = ['routing_slip']

    routing_slip_number = fields.String(data_key='routing_slip_number')
    submitter_name = fields.String(data_key='submitter_display_name')
