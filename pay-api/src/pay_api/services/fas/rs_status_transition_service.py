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
"""Service to manage routing slip status transition operations."""
from __future__ import annotations

from typing import Dict, List

from pay_api.exceptions import BusinessException
from pay_api.utils.enums import RoutingSlipCustomStatus, RoutingSlipStatus
from pay_api.utils.errors import Error


class RsStatusTransitionService:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Service to manage Routing slip status transition related operations."""

    STATUS_TRANSITIONS: Dict[str, List] = {
        RoutingSlipStatus.ACTIVE.value: [
            RoutingSlipStatus.HOLD.value,
            RoutingSlipStatus.NSF.value,
            RoutingSlipStatus.REFUND_REQUESTED.value,
            RoutingSlipStatus.WRITE_OFF_REQUESTED.value
        ],
        RoutingSlipStatus.COMPLETE.value: [
            RoutingSlipStatus.NSF.value
        ],
        RoutingSlipStatus.HOLD.value: [
            RoutingSlipStatus.ACTIVE.value,
            RoutingSlipStatus.NSF.value
        ],
        RoutingSlipStatus.REFUND_REQUESTED.value: [
            RoutingSlipCustomStatus.REVIEW_REFUND_REQUEST.value,
            RoutingSlipCustomStatus.CANCEL_REFUND_REQUEST.value
        ],
        RoutingSlipStatus.REFUND_AUTHORIZED.value: [
        ],
        RoutingSlipStatus.REFUND_COMPLETED.value: [
        ],
        RoutingSlipStatus.LINKED.value: [
        ],

    }

    @classmethod
    def get_possible_transitions(cls, current_status: RoutingSlipStatus) -> List[RoutingSlipStatus]:
        """Return all the status transition available."""
        return RsStatusTransitionService.STATUS_TRANSITIONS.get(current_status, [])

    @classmethod
    def validate_possible_transitions(cls, current_status: RoutingSlipStatus,
                                      future_status: RoutingSlipStatus):
        """Validate if its a legit status transition."""
        allowed_statuses = RsStatusTransitionService.STATUS_TRANSITIONS.get(current_status, [])
        if future_status not in allowed_statuses:
            raise BusinessException(Error.FAS_INVALID_RS_STATUS_CHANGE)
