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
"""Worker resource to handle incoming queue pushes from gcp."""

import dataclasses
import json
from http import HTTPStatus

from flask import Blueprint, current_app, request
from pay_api.services.gcp_queue_publisher import queue
from sbc_common_components.utils.enums import QueueMessageTypes

from pay_queue.external.gcp_auth import ensure_authorized_queue_user
from pay_queue.services import update_temporary_identifier
from pay_queue.services.cgi_reconciliations import reconcile_distributions
from pay_queue.services.eft.eft_reconciliation import reconcile_eft_payments
from pay_queue.services.payment_reconciliations import reconcile_payments


bp = Blueprint('worker', __name__)


@bp.route('/', methods=('POST',))
@ensure_authorized_queue_user
def worker():
    """Worker to handle incoming queue pushes."""
    ce = queue.get_simple_cloud_event(request, wrapped=True)
    if not ce:
        return {}, HTTPStatus.OK

    try:
        current_app.logger.info('Event Message Received: %s ', json.dumps(dataclasses.asdict(ce)))
        if ce.type == QueueMessageTypes.CAS_MESSAGE_TYPE.value:
            reconcile_payments(ce)
        elif ce.type == QueueMessageTypes.CGI_ACK_MESSAGE_TYPE.value:
            reconcile_distributions(ce.data)
        elif ce.type == QueueMessageTypes.CGI_FEEDBACK_MESSAGE_TYPE.value:
            reconcile_distributions(ce.data, is_feedback=True)
        elif ce.type == QueueMessageTypes.EFT_FILE_UPLOADED.value:
            reconcile_eft_payments(ce.data)
        elif ce.type in [QueueMessageTypes.INCORPORATION.value, QueueMessageTypes.REGISTRATION.value]:
            update_temporary_identifier(ce.data)
        else:
            current_app.logger.warning('Invalid queue message type: %s', ce.type)

        return {}, HTTPStatus.OK
    except Exception: # NOQA # pylint: disable=broad-except
        # Catch Exception so that any error is still caught and the message is removed from the queue
        current_app.logger.error('Error processing event:', exc_info=True)
        return {}, HTTPStatus.OK
