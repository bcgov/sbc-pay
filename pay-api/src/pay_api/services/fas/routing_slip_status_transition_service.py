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
from pay_api.utils.user_context import user_context
from pay_api.models import Refund as RefundModel
from pay_api.models import RoutingSlip as RoutingSlipModel


class RoutingSlipStatusTransitionService:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Service to manage Routing slip status transition related operations."""

    STATUS_TRANSITIONS: Dict[str, List] = {
        RoutingSlipStatus.ACTIVE.value: [
            RoutingSlipStatus.HOLD.value,
            RoutingSlipStatus.NSF.value,
            RoutingSlipStatus.REFUND_REQUESTED.value,
            RoutingSlipStatus.WRITE_OFF_REQUESTED.value,
            RoutingSlipStatus.VOID.value,
            RoutingSlipStatus.CORRECTION.value
        ],
        RoutingSlipStatus.COMPLETE.value: [
            RoutingSlipStatus.NSF.value,
            RoutingSlipStatus.VOID.value,
            RoutingSlipStatus.CORRECTION.value
        ],
        RoutingSlipStatus.HOLD.value: [
            RoutingSlipStatus.ACTIVE.value,
            RoutingSlipStatus.NSF.value,
            RoutingSlipStatus.VOID.value
        ],
        RoutingSlipStatus.REFUND_REQUESTED.value: [
            RoutingSlipStatus.REFUND_AUTHORIZED.value,
            RoutingSlipCustomStatus.CANCEL_REFUND_REQUEST.custom_status  # pylint: disable=no-member
        ],
        RoutingSlipStatus.WRITE_OFF_REQUESTED.value: [
            RoutingSlipStatus.WRITE_OFF_AUTHORIZED.value,
            RoutingSlipCustomStatus.CANCEL_WRITE_OFF_REQUEST.custom_status  # pylint: disable=no-member
        ],
        RoutingSlipStatus.REFUND_AUTHORIZED.value: [
        ],
        RoutingSlipStatus.REFUND_COMPLETED.value: [
        ],
        RoutingSlipStatus.LINKED.value: [
        ],
        RoutingSlipStatus.VOID.value: [
        ],
        RoutingSlipStatus.CORRECTION.value: [
            RoutingSlipStatus.CORRECTION.value
        ]

    }

    @classmethod
    @user_context
    def get_possible_transitions(cls, rs_model: RoutingSlipModel, **kwargs) -> List[RoutingSlipStatus]:
        """Return all the status transition available."""
        transition_list: List[RoutingSlipStatus] = RoutingSlipStatusTransitionService.STATUS_TRANSITIONS.get(
            rs_model.status, [])

        if RoutingSlipStatus.REFUND_AUTHORIZED.value in transition_list:
            # self approval not permitted
            refund_model = RefundModel.find_by_routing_slip_id(rs_model.id)
            is_same_user = refund_model.requested_by == kwargs['user'].user_name
            if is_same_user:
                return transition_list[1:]
        elif RoutingSlipStatus.WRITE_OFF_AUTHORIZED.value in transition_list:
            is_same_user = rs_model.updated_by == kwargs['user'].user_name
            if is_same_user:
                return transition_list[1:]

        return transition_list

    @classmethod
    def validate_possible_transitions(cls, rs_model: RoutingSlipModel,
                                      future_status: RoutingSlipStatus):
        """Validate if its a legit status transition."""
        allowed_statuses = RoutingSlipStatusTransitionService.get_possible_transitions(rs_model)
        if future_status not in allowed_statuses:
            raise BusinessException(Error.FAS_INVALID_RS_STATUS_CHANGE)

    @classmethod
    def get_actual_status(cls, status):
        """Return actual status if it's a custom status enum."""
        custom: RoutingSlipCustomStatus = RoutingSlipCustomStatus.from_key(status)
        return custom.original_status if custom else status
