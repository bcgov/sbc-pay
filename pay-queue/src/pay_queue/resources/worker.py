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
from http import HTTPStatus

from flask import Blueprint, request
from pay_api.utils.enums import MessageType

from pay_queue.external.gcp_auth import ensure_authorized_queue_user
from pay_queue.services import queue, update_temporary_identifier
from pay_queue.services.cgi_reconciliations import reconcile_distributions
from pay_queue.services.eft.eft_reconciliation import reconcile_eft_payments
from pay_queue.services.payment_reconciliations import reconcile_payments


bp = Blueprint('worker', __name__)


@bp.route('/', methods=('POST',))
@ensure_authorized_queue_user
def worker():
    """Worker to handle incoming queue pushes."""
    if not (ce := queue.get_simple_cloud_event(request)):
        # Return a 200, so event is removed from the Queue
        return {}, HTTPStatus.OK

    match ce.type:
        case MessageType.CAS_UPLOADED.value:
            reconcile_payments(ce.data)
        case MessageType.CGI_ACK_RECEIVED.value:
            reconcile_distributions(ce.data)
        case MessageType.CGI_FEEDBACK_RECEIVED.value:
            reconcile_distributions(ce.data, is_feedback=True)
        case MessageType.EFT_FILE_UPLOADED.value:
            reconcile_eft_payments(ce.data)
        case MessageType.INCORPORATION.value | MessageType.REGISTRATION.value:
            update_temporary_identifier(ce.data)
        case _:
            raise Exception('Invalid queue message type')  # pylint: disable=broad-exception-raised

    return {}, HTTPStatus.OK
