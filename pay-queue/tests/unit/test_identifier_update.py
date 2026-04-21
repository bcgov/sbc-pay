# Copyright © 2026 Province of British Columbia
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

"""Unit tests for update_temporary_identifier service."""

from pay_api.models import Invoice
from pay_api.utils.enums import PaymentMethod, PaymentSystem
from pay_queue.services.identifier_updater import update_temporary_identifier
from tests.integration import factory_invoice, factory_payment_account


def test_update_temporary_identifier_missing_key(session, app):
    """Assert missing tempidentifier key in message results in early return without modifying invoices."""
    payment_account = factory_payment_account(payment_system_code=PaymentSystem.BCOL.value).save()
    invoice = factory_invoice(payment_account=payment_account, business_identifier="T1234567").save()

    update_temporary_identifier({"identifier": "BC1234567"})

    assert Invoice.find_by_id(invoice.id).business_identifier == "T1234567"


def test_update_temporary_identifier_none_value(session, app):
    """Assert none tempIdentifier results in early return without modifying invoices."""
    payment_account = factory_payment_account(payment_system_code=PaymentSystem.BCOL.value).save()
    invoice = factory_invoice(payment_account=payment_account, business_identifier="T1234567").save()

    update_temporary_identifier({"tempidentifier": None, "identifier": "BC1234567"})

    assert Invoice.find_by_id(invoice.id).business_identifier == "T1234567"


def test_update_temporary_identifier_updates_invoice(session, app):
    """A matching invoice has its business_identifier updated to the permanent identifier."""
    old_identifier = "T1234567"
    new_identifier = "BC1234567"

    payment_account = factory_payment_account(payment_system_code=PaymentSystem.BCOL.value).save()
    invoice = factory_invoice(
        payment_account=payment_account,
        business_identifier=old_identifier,
        payment_method_code=PaymentMethod.DIRECT_PAY.value,
    ).save()

    update_temporary_identifier({"tempidentifier": old_identifier, "identifier": new_identifier})

    assert Invoice.find_by_id(invoice.id).business_identifier == new_identifier
