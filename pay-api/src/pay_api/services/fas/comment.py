# Copyright © 2024 Province of British Columbia
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

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import Comment as CommentModel
from pay_api.models import CommentSchema
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.utils.errors import Error


class Comment:
    """Service to manage Routing slip comments related operations."""

    @classmethod
    def asdict(cls, dao) -> dict[str]:
        """Return the comment as a python dict."""
        comment_schema = CommentSchema()
        d = comment_schema.dump(dao)
        return d

    @classmethod
    def find_all_comments_for_a_routingslip(cls, routing_slip_number: str):
        """Find comments for a routing slip."""
        current_app.logger.debug("<Comment.get.service")
        if (routing_slip := RoutingSlipModel.find_by_number(routing_slip_number)) is None:
            raise BusinessException(Error.FAS_INVALID_ROUTING_SLIP_NUMBER)

        comments_dao = CommentModel.find_all_comments_for_a_routingslip(routing_slip.number)
        comments = CommentSchema().dump(comments_dao, many=True)
        current_app.logger.debug(">Comment.get.service")
        return {"comments": comments}

    @classmethod
    def create(cls, comment_value: str, rs_number: str):
        """Create routing slip comment."""
        current_app.logger.debug("<Comment.create.service")
        if RoutingSlipModel.find_by_number(number=rs_number) is None:
            raise BusinessException(Error.FAS_INVALID_ROUTING_SLIP_NUMBER)

        comment = CommentModel(comment=comment_value, routing_slip_number=rs_number).flush()
        comment.commit()
        current_app.logger.debug(">Comment.create.service")
        return cls.asdict(comment)
