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
"""Updates the temporary identifier to a permanent identifier in the invoice table."""
from flask import current_app
from pay_api.models import db
from pay_api.models.invoice import Invoice


def update_temporary_identifier(event_message):
    """Update a temporary identifier to a permanent identifier."""
    if "tempidentifier" not in event_message or event_message.get("tempidentifier", None) is None:
        return

    old_identifier = event_message.get("tempidentifier")
    new_identifier = event_message.get("identifier")
    current_app.logger.debug("Received message to update %s to %s", old_identifier, new_identifier)

    invoices = Invoice.find_by_business_identifier(old_identifier)
    for inv in invoices:
        inv.business_identifier = new_identifier
        inv.flush()

    db.session.commit()
