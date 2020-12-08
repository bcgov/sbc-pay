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

import pytz

from pay_api.models.payment_account import PaymentAccount
from pay_api.services.payment import Payment as Payment_service
from pay_api.utils.enums import InvoiceStatus, InvoiceReferenceStatus, PaymentMethod
from tests.utilities.base_test import (
    factory_invoice, factory_payment_line_item, factory_invoice_reference, factory_payment, factory_payment_account)


def test_payment_saved_from_new(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    p = Payment_service.find_by_id(payment.id)

    assert p is not None
    assert p.id is not None
    assert p.payment_system_code is not None
    assert p.payment_method_code is not None
    assert p.payment_status_code is not None


def test_payment_invalid_lookup(session):
    """Test invalid lookup."""
    p = Payment_service.find_by_id(999)

    assert p is not None
    assert p.id is None


def test_payment_with_no_active_invoice(session):
    """Assert that the payment is saved to the table."""
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account, InvoiceStatus.DELETED.value)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    p = Payment_service.find_by_id(payment.id)

    assert p is not None
    assert p.id is not None


def test_search_payment_history(session):
    """Assert that the search payment history is working."""
    payment_account = factory_payment_account()
    payment_account.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter={}, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 1

    # Add one more payment
    payment_account.save()
    invoice = factory_invoice(payment_account)
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

    # TODO
    # # Search by different filter
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
        'createdBy': invoice.created_name
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
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    for i in range(20):
        payment = factory_payment(payment_status_code='CREATED')
        payment.save()
        invoice = factory_invoice(payment_account)
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
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    for i in range(20):
        payment = factory_payment(payment_status_code='CREATED')
        payment.save()
        invoice = factory_invoice(payment_account)
        invoice.save()
        factory_invoice_reference(invoice.id).save()

    Payment_service.create_payment_report(auth_account_id=auth_account_id, search_filter={},
                                          content_type='text/csv', report_name='test')
    assert True  # If no error, then good


def test_create_payment_report_pdf(session, rest_call_mock):
    """Assert that the create payment report is working."""
    payment_account = factory_payment_account()
    payment_account.save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    for i in range(20):
        payment = factory_payment(payment_status_code='CREATED')
        payment.save()
        invoice = factory_invoice(payment_account)
        invoice.save()
        factory_invoice_reference(invoice.id).save()

    Payment_service.create_payment_report(auth_account_id=auth_account_id, search_filter={},
                                          content_type='application/pdf', report_name='test')
    assert True  # If no error, then good


def test_search_payment_history_with_tz(session):
    """Assert that the search payment history is working."""
    payment_account = factory_payment_account()
    invoice_created_on = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    invoice_created_on = invoice_created_on.astimezone(pytz.utc)
    payment = factory_payment(payment_status_code='CREATED')
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account, created_on=invoice_created_on)
    invoice.save()
    factory_invoice_reference(invoice.id).save()
    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter={}, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 1

    # Add one more payment
    invoice_created_on = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    invoice_created_on = invoice_created_on.astimezone(pytz.utc)
    payment = factory_payment(payment_status_code='CREATED')
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account, created_on=invoice_created_on)
    invoice.save()
    factory_invoice_reference(invoice.id).save()

    results = Payment_service.search_purchase_history(auth_account_id=auth_account_id,
                                                      search_filter={}, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 2


def test_search_account_payments(session):
    """Assert that the search account payments is working."""
    inv_number = 'REG00001'
    payment_account = factory_payment_account().save()

    invoice_1 = factory_invoice(payment_account)
    invoice_1.save()
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number).save()

    payment_created_on = datetime.now()
    payment_1 = factory_payment(payment_status_code='CREATED',
                                payment_account_id=payment_account.id, invoice_number=inv_number,
                                payment_method_code=PaymentMethod.PAD.value)
    payment_1.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = Payment_service.search_account_payments(auth_account_id=auth_account_id,
                                                      status=None, limit=1, page=1)
    assert results is not None
    assert results.get('items') is not None
    assert results.get('total') == 1


def test_search_account_failed_payments(session):
    """Assert that the search account payments is working."""
    inv_number_1 = 'REG00001'
    payment_account = factory_payment_account().save()

    invoice_1 = factory_invoice(payment_account)
    invoice_1.save()
    inv_ref_1 = factory_invoice_reference(invoice_1.id, invoice_number=inv_number_1).save()

    payment_1 = factory_payment(payment_status_code='FAILED',
                                payment_account_id=payment_account.id, invoice_number=inv_number_1,
                                payment_method_code=PaymentMethod.PAD.value)
    payment_1.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = Payment_service.search_account_payments(auth_account_id=auth_account_id,
                                                      status='FAILED', limit=1, page=1)
    assert results.get('items')
    assert results.get('total') == 1

    # Create one more payment with failed status.
    inv_number_2 = 'REG00002'
    invoice_2 = factory_invoice(payment_account)
    invoice_2.save()
    inv_ref_2 = factory_invoice_reference(invoice_2.id, invoice_number=inv_number_2).save()

    payment_2 = factory_payment(payment_status_code='FAILED',
                                payment_account_id=payment_account.id, invoice_number=inv_number_2,
                                payment_method_code=PaymentMethod.PAD.value)
    payment_2.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = Payment_service.search_account_payments(auth_account_id=auth_account_id,
                                                      status='FAILED', limit=1, page=1)
    assert results.get('items')
    assert results.get('total') == 2

    # Now combine both payments into one, by setting status to invoice reference. - NSF payments
    inv_ref_1.status_code = InvoiceReferenceStatus.CANCELLED.value
    inv_ref_2.status_code = InvoiceReferenceStatus.CANCELLED.value
    inv_ref_1.save()
    inv_ref_2.save()

    # Now create new invoice reference for consolidated invoice
    inv_number_3 = 'REG00003'
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number_3).save()
    factory_invoice_reference(invoice_2.id, invoice_number=inv_number_3).save()
    results = Payment_service.search_account_payments(auth_account_id=auth_account_id,
                                                      status='FAILED', limit=1, page=1)
    # Now there are no active failed payments, so it should return zero records
    assert not results.get('items')
    assert results.get('total') == 0


def test_create_account_payments_for_one_failed_payment(session):
    """Assert that the create account payments is working."""
    inv_number_1 = 'REG00001'
    payment_account = factory_payment_account().save()
    invoice_1 = factory_invoice(payment_account)
    invoice_1.save()
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number_1).save()
    payment_1 = factory_payment(payment_status_code='FAILED',
                                payment_account_id=payment_account.id, invoice_number=inv_number_1,
                                payment_method_code=PaymentMethod.PAD.value)
    payment_1.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = Payment_service.search_account_payments(auth_account_id=auth_account_id,
                                                      status='FAILED', limit=1, page=1)
    assert results.get('total') == 1

    new_payment = Payment_service.create_account_payment(auth_account_id=auth_account_id, is_retry_payment=True)
    old_payment = Payment_service.find_by_id(payment_1.id)
    # Assert new payment invoice number is same as old payment as there is only one failed payment.
    assert new_payment.invoice_number == old_payment.invoice_number


def test_create_account_payments_for_multiple_failed_payments(session):
    """Assert that the create account payments is working."""
    inv_number_1 = 'REG00001'
    payment_account = factory_payment_account().save()
    invoice_1 = factory_invoice(payment_account, total=100)
    invoice_1.save()
    factory_payment_line_item(invoice_id=invoice_1.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number_1).save()
    payment_1 = factory_payment(payment_status_code='FAILED',
                                payment_account_id=payment_account.id,
                                invoice_number=inv_number_1,
                                invoice_amount=100,
                                payment_method_code=PaymentMethod.PAD.value)
    payment_1.save()

    # Create one more payment with failed status.
    inv_number_2 = 'REG00002'
    invoice_2 = factory_invoice(payment_account, total=100)
    invoice_2.save()
    factory_payment_line_item(invoice_id=invoice_2.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_2.id, invoice_number=inv_number_2).save()

    payment_2 = factory_payment(payment_status_code='FAILED',
                                payment_account_id=payment_account.id,
                                invoice_number=inv_number_2,
                                invoice_amount=100,
                                payment_method_code=PaymentMethod.PAD.value)
    payment_2.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = Payment_service.search_account_payments(auth_account_id=auth_account_id,
                                                      status='FAILED', limit=10, page=1)
    assert results.get('total') == 2

    new_payment = Payment_service.create_account_payment(auth_account_id=auth_account_id, is_retry_payment=True)
    payment_1 = Payment_service.find_by_id(payment_1.id)
    payment_2 = Payment_service.find_by_id(payment_2.id)
    # Assert new payment invoice number is different from old payment as there are more than one failed payments.
    assert new_payment.invoice_number != payment_1.invoice_number
    assert new_payment.invoice_number != payment_2.invoice_number
    assert payment_1.cons_inv_number == new_payment.invoice_number
    assert payment_2.cons_inv_number == new_payment.invoice_number
    assert new_payment.invoice_amount == payment_1.invoice_amount + payment_2.invoice_amount


def test_create_account_payments_after_consolidation(session):
    """Assert creating account payments after consolidation yields same payment record."""
    inv_number_1 = 'REG00001'
    payment_account = factory_payment_account().save()
    invoice_1 = factory_invoice(payment_account, total=100)
    invoice_1.save()
    factory_payment_line_item(invoice_id=invoice_1.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number_1).save()
    payment_1 = factory_payment(payment_status_code='FAILED',
                                payment_account_id=payment_account.id,
                                invoice_number=inv_number_1,
                                invoice_amount=100,
                                payment_method_code=PaymentMethod.PAD.value)
    payment_1.save()

    # Create one more payment with failed status.
    inv_number_2 = 'REG00002'
    invoice_2 = factory_invoice(payment_account, total=100)
    invoice_2.save()
    factory_payment_line_item(invoice_id=invoice_2.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_2.id, invoice_number=inv_number_2).save()
    payment_2 = factory_payment(payment_status_code='FAILED',
                                payment_account_id=payment_account.id,
                                invoice_number=inv_number_2,
                                invoice_amount=100,
                                payment_method_code=PaymentMethod.PAD.value)
    payment_2.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = Payment_service.search_account_payments(auth_account_id=auth_account_id,
                                                      status='FAILED', limit=10, page=1)
    assert results.get('total') == 2

    new_payment_1 = Payment_service.create_account_payment(auth_account_id=auth_account_id, is_retry_payment=True)
    # Create account payment again and assert both payments returns same.
    new_payment_2 = Payment_service.create_account_payment(auth_account_id=auth_account_id, is_retry_payment=True)

    assert new_payment_1.id == new_payment_2.id


def test_failed_payment_after_consolidation(session):
    """Assert creating account payments after consolidation works."""
    # Create 2 failed payments, consolidate it, and then again create another failed payment.
    # Consolidate it and make sure amount matches.
    inv_number_1 = 'REG00001'
    payment_account = factory_payment_account().save()
    invoice_1 = factory_invoice(payment_account, total=100)
    invoice_1.save()
    factory_payment_line_item(invoice_id=invoice_1.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_1.id, invoice_number=inv_number_1).save()
    payment_1 = factory_payment(payment_status_code='FAILED',
                                payment_account_id=payment_account.id,
                                invoice_number=inv_number_1,
                                invoice_amount=100,
                                payment_method_code=PaymentMethod.PAD.value)
    payment_1.save()

    # Create one more payment with failed status.
    inv_number_2 = 'REG00002'
    invoice_2 = factory_invoice(payment_account, total=100)
    invoice_2.save()
    factory_payment_line_item(invoice_id=invoice_2.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_2.id, invoice_number=inv_number_2).save()
    payment_2 = factory_payment(payment_status_code='FAILED',
                                payment_account_id=payment_account.id,
                                invoice_number=inv_number_2,
                                invoice_amount=100,
                                payment_method_code=PaymentMethod.PAD.value)
    payment_2.save()

    auth_account_id = PaymentAccount.find_by_id(payment_account.id).auth_account_id

    results = Payment_service.search_account_payments(auth_account_id=auth_account_id,
                                                      status='FAILED', limit=10, page=1)
    assert results.get('total') == 2

    new_payment_1 = Payment_service.create_account_payment(auth_account_id=auth_account_id, is_retry_payment=True)

    # Create another failed payment.
    inv_number_3 = 'REG00003'
    invoice_3 = factory_invoice(payment_account, total=100)
    invoice_3.save()
    factory_payment_line_item(invoice_id=invoice_3.id, fee_schedule_id=1).save()
    factory_invoice_reference(invoice_3.id, invoice_number=inv_number_3).save()
    payment_3 = factory_payment(payment_status_code='FAILED',
                                payment_account_id=payment_account.id,
                                invoice_number=inv_number_3,
                                invoice_amount=100,
                                payment_method_code=PaymentMethod.PAD.value)
    payment_3.save()

    new_payment_2 = Payment_service.create_account_payment(auth_account_id=auth_account_id, is_retry_payment=True)
    assert new_payment_1.id != new_payment_2.id
    assert new_payment_2.invoice_amount == payment_1.invoice_amount + payment_2.invoice_amount + \
           payment_3.invoice_amount
