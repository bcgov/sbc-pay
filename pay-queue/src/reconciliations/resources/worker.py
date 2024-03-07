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
from http import HTTPStatus
from flask import Blueprint, current_app, request, abort
from requests.sessions import Session
from google.auth.transport.requests import Request
import google.oauth2.id_token as id_token
import functools
from ..services import queue
from reconciliations.services.cgi_reconciliations import reconcile_distributions
from reconciliations.eft.eft_reconciliation import reconcile_eft_payments
from reconciliations.enums import MessageType
from reconciliations.services.payment_reconciliations import reconcile_payments
from cachecontrol import CacheControl
bp = Blueprint('worker', __name__)

def verify_jwt(session):
    """Verify token is valid."""
    msg = ''
    try:
        # Get the Cloud Pub/Sub-generated JWT in the "Authorization" header.
        id_token.verify_oauth2_token(
            request.headers.get("Authorization").split()[1],
            Request(session=session),
            audience=current_app.config.get("PAY_SUB_AUDIENCE")
        )
    except Exception as e:  # TODO fix
        msg = f"Invalid token: {e}\n"
    finally:
        return msg


def ensure_authorized_queue_user(f):
    """Ensures the user is authorized to use the queue."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Use CacheControl to avoid re-fetching certificates for every request.
        if message := verify_jwt(CacheControl(Session())):
            print(message)
            abort(400)
        return f(*args, **kwargs)
    return decorated_function


@bp.route("/", methods=("POST",))
@ensure_authorized_queue_user
async def worker():
    """Worker to handle incoming queue pushes."""
    if not (ce := queue.get_simple_cloud_event(request)):
        # Return a 200, so event is removed from the Queue
        return {}, HTTPStatus.OK

    if (message_type := ce.get('type', None)) == MessageType.CAS_UPLOADED.value:
        await reconcile_payments(ce)
    elif message_type == MessageType.CGI_ACK_RECEIVED.value:
        await reconcile_distributions(ce)
    elif message_type == MessageType.CGI_FEEDBACK_RECEIVED.value:
        await reconcile_distributions(ce, is_feedback=True)
    elif message_type == MessageType.EFT_FILE_UPLOADED.value:
        await reconcile_eft_payments(ce)
    else:
        raise Exception('Invalid type')  # pylint: disable=broad-exception-raised
