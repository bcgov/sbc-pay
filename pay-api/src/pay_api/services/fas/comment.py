# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Service to manage routing slip comments."""
from __future__ import annotations

from datetime import datetime
from typing import Dict

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import Comment as CommentModel
from pay_api.models import CommentSchema
from pay_api.utils.errors import Error


class Comment:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Service to manage Routing slip comments related operations."""

    def __init__(self):
        """Initialize the service."""
        self.__dao = None
        self._id: int = None
        self._comment: str = None
        self._timestamp: datetime = None
        self._routing_slip_number: str = None
        self._submitter_name: str = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = CommentModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao: CommentModel = value
        self.id: int = self._dao.id
        self.comment: str = self._dao.comment
        self.timestamp: datetime = self._dao.timestamp
        self.routing_slip_number: str = self._dao.routing_slip_number
        self.submitter_name: str = self._dao.submitter_name

    @property
    def id(self):
        """Return the _id."""
        return self._id

    @id.setter
    def id(self, value: int):
        """Set the id."""
        self._id = value
        self._dao.id = value

    @property
    def comment(self):
        """Return the comment."""
        return self._comment

    @comment.setter
    def comment(self, value: str):
        """Set the comment."""
        self._comment = value
        self._dao.comment = value

    @property
    def timestamp(self):
        """Return the timestamp."""
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value: datetime):
        """Set the time_stamp."""
        self._timestamp = value
        self._dao.timestamp = value

    @property
    def routing_slip_number(self):
        """Return the payment_account_id."""
        return self._routing_slip_number

    @routing_slip_number.setter
    def routing_slip_number(self, value: str):
        """Set the routingslip number reference."""
        self._routing_slip_number = value
        self._dao.routing_slip_number = value

    @property
    def submitter_name(self):
        """Return the submitted by staff user name."""
        return self._submitter_name

    @submitter_name.setter
    def submitter_name(self, value: str):
        """Set the submitted by staff user name."""
        self._submitter_name = value
        self._dao.submitter_name = value

    def commit(self):
        """Save the information to the DB."""
        return self._dao.commit()

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    def rollback(self):
        """Rollback."""
        return self._dao.rollback()

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    def asdict(self) -> Dict[str]:
        """Return the comment as a python dict."""
        comment_schema = CommentSchema()
        d = comment_schema.dump(self._dao)
        return d

    @classmethod
    def find_all_comments_for_a_routingslip(cls, routing_slip_number: str):
        """Find comments for a routing slip."""
        current_app.logger.debug('<Comment.get.service')
        routing_slip: RoutingSlipModel = RoutingSlipModel.find_by_number(routing_slip_number)

        if routing_slip is None:
            raise BusinessException(Error.FAS_INVALID_ROUTING_SLIP_NUMBER)

        comments_dao = CommentModel.find_all_comments_for_a_routingslip(routing_slip.number)
        comments = CommentSchema().dump(comments_dao, many=True)
        data = {
            'comments': comments
        }

        current_app.logger.debug('>Comment.get.service')
        return data

    @classmethod
    def create(cls, comment_value: str, rs_number: str):
        """Create routing slip comment."""
        current_app.logger.debug('<Comment.create.service')
        routing_slip: RoutingSlipModel = RoutingSlipModel.find_by_number(number=rs_number)
        if routing_slip is None:
            raise BusinessException(Error.FAS_INVALID_ROUTING_SLIP_NUMBER)

        # Create a routing slip comment record.
        comment_service = Comment()
        comment_service._dao = CommentModel(
            comment=comment_value,
            routing_slip_number=rs_number
        )
        comment_service.flush()

        comment_service.commit()
        current_app.logger.debug('>Comment.create.service')
        return comment_service.asdict()
