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

"""Tests to assure the FeeSchedule Service.

Test-Suite to ensure that the FeeSchedule Service is working as expected.
"""
from datetime import datetime

from pay_api.models.payment_account import PaymentAccount
from pay_api.services.payment import Payment as Payment_service
from pay_api.utils.enums import InvoiceStatus
from tests.utilities.base_test import (
    factory_invoice, factory_invoice_reference, factory_payment, factory_payment_account)
import pytz


def test_payment_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment, payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    p = Payment_service.find_by_id(payment.id, skip_auth_check=True)

    assert p is not None
    assert p.id is not None
    assert p.payment_system_code is not None
    assert p.payment_method_code is not None
    assert p.payment_status_code is not None
    assert p.invoices is not None


def test_payment_invalid_lookup(session):
    """Test invalid lookup."""
    p = Payment_service.find_by_id(999, skip_auth_check=True)

    assert p is not None
    assert p.id is None


def test_payment_with_no_active_invoice(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment, payment_account, InvoiceStatus.DELETED.value)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    p = Payment_service.find_by_id(payment.id, skip_auth_check=True)

    assert p is not None
    assert p.id is not None


def test_search_payment_history(session):
    """Assert that the search payment history is working."""
    payment_account = factory_payment_account()
    payment = factory_payment(payment_status_code='CREATED')
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment, payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.account_id).auth_account_id

    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter={}, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 1

    # Add one more payment
    payment = factory_payment(payment_status_code='CREATED')
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment, payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()

    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter={}, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 2

    # Search by different filter
    search_filter = {
        'status': 'CREATED'
    }
    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter=search_filter, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 2

    # Search by different filter
    search_filter = {
        'status': 'COMPLETED'
    }
    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter=search_filter, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 0

    # Search by different filter
    search_filter = {
        'folioNumber': '1234567890'
    }
    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter=search_filter, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 2

    # Search by different filter
    search_filter = {
        'businessIdentifier': invoice.business_identifier
    }
    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter=search_filter, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 2

    # Search by different filter
    search_filter = {
        'dateFilter': {
            'createdFrom': datetime.now().strftime('%m/%d/%Y'),
            'createdTo': datetime.now().strftime('%m/%d/%Y')
        }
    }
    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter=search_filter, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 2

    # Search by different filter
    search_filter = {
        'weekFilter': {
            'index': 2
        }
    }
    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter=search_filter, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 0

    # Search by different filter
    search_filter = {
        'monthFilter': {
            'month': datetime.now().month,
            'year': datetime.now().year
        }
    }
    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter=search_filter, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 2

    # Search by different filter
    search_filter = {
        'createdBy': payment.created_name
    }
    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter=search_filter, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 2


def test_search_payment_history_for_all(session):
    """Assert that the search payment history is working."""
    payment_account = factory_payment_account()
    payment_account.save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.account_id).auth_account_id

    for i in range(20):
        payment = factory_payment(payment_status_code='CREATED')
        payment.save()
        invoice = factory_invoice(payment, payment_account)
        invoice.save()
        factory_invoice_reference(invoice.id).save()

    results = Payment_service.search_all_purchase_history(auth_account_id=auth_account_id, search_filter={})
    assert results is not None
    assert results.get('items') is not None
    # Returns only the default number if payload is empty
    assert results.get('total') == 10


def test_create_payment_report_csv(session, rest_call_mock):
    """Assert that the create payment report is working."""
    payment_account = factory_payment_account()
    payment_account.save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.account_id).auth_account_id

    for i in range(20):
        payment = factory_payment(payment_status_code='CREATED')
        payment.save()
        invoice = factory_invoice(payment, payment_account)
        invoice.save()
        factory_invoice_reference(invoice.id).save()

    Payment_service.create_payment_report(auth_account_id=auth_account_id, search_filter={},
                                          content_type='text/csv', report_name='test')
    assert True  # If no error, then good


def test_create_payment_report_pdf(session, rest_call_mock):
    """Assert that the create payment report is working."""
    payment_account = factory_payment_account()
    payment_account.save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.account_id).auth_account_id

    for i in range(20):
        payment = factory_payment(payment_status_code='CREATED')
        payment.save()
        invoice = factory_invoice(payment, payment_account)
        invoice.save()
        factory_invoice_reference(invoice.id).save()

    Payment_service.create_payment_report(auth_account_id=auth_account_id, search_filter={},
                                          content_type='application/pdf', report_name='test')
    assert True  # If no error, then good


def test_search_payment_history_with_tz(session):
    """Assert that the search payment history is working."""
    payment_account = factory_payment_account()
    payment_created_on = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    payment_created_on = payment_created_on.astimezone(pytz.utc)
    payment = factory_payment(payment_status_code='CREATED', created_on=payment_created_on)
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment, payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.account_id).auth_account_id

    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter={}, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 1

    # Add one more payment
    payment_created_on = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    payment_created_on = payment_created_on.astimezone(pytz.utc)
    payment = factory_payment(payment_status_code='CREATED', created_on=payment_created_on)
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment, payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()

    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter={}, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 2
