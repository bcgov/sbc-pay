# Copyright © 2019 Province of British Columbia
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
"""Test Suite to ensure the worker routines are working as expected."""

import pytest
from entity_queue_common.service_utils import subscribe_to_queue
from pay_api.models import Invoice
from pay_api.utils.enums import PaymentMethod, PaymentSystem

from tests.integration import factory_invoice, factory_invoice_reference, factory_payment, factory_payment_account

from .utils import helper_add_event_to_queue


@pytest.mark.asyncio
async def test_events_listener_queue(app, session, stan_server, event_loop, client_id, events_stan, future):
    """Assert that events can be retrieved and decoded from the Queue."""
    # Call back for the subscription
    from events_listener.worker import cb_subscription_handler

    # vars
    old_identifier = 'T000000000'
    new_identifier = 'BC12345678'

    events_subject = 'test_subject'
    events_queue = 'test_queue'
    events_durable_name = 'test_durable'

    # Create a Credit Card Payment

    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             events_subject,
                             events_queue,
                             events_durable_name,
                             cb_subscription_handler)

    # add an event to queue
    await helper_add_event_to_queue(events_stan, events_subject, old_identifier=old_identifier,
                                    new_identifier=new_identifier)

    assert True


@pytest.mark.asyncio
async def test_update_internal_payment(app, session, stan_server, event_loop, client_id, events_stan, future):
    """Assert that the update internal payment records works."""
    # Call back for the subscription
    from events_listener.worker import cb_subscription_handler

    # vars
    old_identifier = 'T000000000'
    new_identifier = 'BC12345678'

    events_subject = 'test_subject'
    events_queue = 'test_queue'
    events_durable_name = 'test_durable'

    # Create an Internal Payment
    payment_account = factory_payment_account(payment_system_code=PaymentSystem.BCOL.value).save()

    invoice: Invoice = factory_invoice(payment_account=payment_account,
                                       business_identifier=old_identifier,
                                       payment_method_code=PaymentMethod.INTERNAL.value).save()

    inv_ref = factory_invoice_reference(invoice_id=invoice.id)
    factory_payment(invoice_number=inv_ref.invoice_number)

    invoice_id = invoice.id

    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             events_subject,
                             events_queue,
                             events_durable_name,
                             cb_subscription_handler)

    # add an event to queue
    await helper_add_event_to_queue(events_stan, events_subject, old_identifier=old_identifier,
                                    new_identifier=new_identifier)

    # Get the internal account and invoice and assert that the identifier is new identifier
    invoice = Invoice.find_by_id(invoice_id)

    assert invoice.business_identifier == new_identifier


@pytest.mark.asyncio
async def test_update_credit_payment(app, session, stan_server, event_loop, client_id, events_stan, future):
    """Assert that the update credit payment records works."""
    # Call back for the subscription
    from events_listener.worker import cb_subscription_handler

    # vars
    old_identifier = 'T000000000'
    new_identifier = 'BC12345678'

    events_subject = 'test_subject'
    events_queue = 'test_queue'
    events_durable_name = 'test_durable'

    # Create an Internal Payment

    payment_account = factory_payment_account(payment_system_code=PaymentSystem.PAYBC.value,
                                              payment_method_code=PaymentMethod.DIRECT_PAY.value).save()

    invoice: Invoice = factory_invoice(payment_account=payment_account,
                                       business_identifier=old_identifier,
                                       payment_method_code=PaymentMethod.DIRECT_PAY.value).save()

    inv_ref = factory_invoice_reference(invoice_id=invoice.id)
    factory_payment(invoice_number=inv_ref.invoice_number)

    invoice_id = invoice.id

    # register the handler to test it
    await subscribe_to_queue(events_stan,
                             events_subject,
                             events_queue,
                             events_durable_name,
                             cb_subscription_handler)

    # add an event to queue
    await helper_add_event_to_queue(events_stan, events_subject, old_identifier=old_identifier,
                                    new_identifier=new_identifier)

    # Get the internal account and invoice and assert that the identifier is new identifier
    invoice = Invoice.find_by_id(invoice_id)

    assert invoice.business_identifier == new_identifier
