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

"""Tests to assure the Statement Service.

Test-Suite to ensure that the Statement Service is working as expected.
"""

from pay_api.models import PaymentAccount
from pay_api.services.statement import Statement as StatementService
from pay_api.utils.enums import StatementFrequency
from tests.utilities.base_test import (
    factory_invoice, factory_invoice_reference, factory_payment, factory_payment_line_item,
    factory_statement,
    factory_premium_payment_account, factory_statement_invoices, factory_statement_settings, get_auth_premium_user)


def test_statement_find_by_account(session):
    """Assert that the statement settings by id works."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment=payment, payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()

    settings_model = factory_statement_settings(payment_account_id=bcol_account.id,
                                                frequency=StatementFrequency.DAILY.value)
    statement_model = factory_statement(payment_account_id=bcol_account.id,
                                        frequency=StatementFrequency.DAILY.value,
                                        statement_settings_id=settings_model.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=i.id)

    payment_account = PaymentAccount.find_by_id(bcol_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None
    assert statements.get('total') == 1


def test_get_statement_report(session):
    """Assert that the get statement report works."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment=payment, payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_payment_line_item(invoice_id=i.id, fee_schedule_id=1).save()

    settings_model = factory_statement_settings(payment_account_id=bcol_account.id,
                                                frequency=StatementFrequency.DAILY.value)
    statement_model = factory_statement(payment_account_id=bcol_account.id,
                                        frequency=StatementFrequency.DAILY.value,
                                        statement_settings_id=settings_model.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=i.id)

    payment_account = PaymentAccount.find_by_id(bcol_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None

    report_response, report_name = StatementService.get_statement_report(statement_id=statement_model.id,
                                                                         content_type='application/pdf',
                                                                         auth=get_auth_premium_user())
    assert report_response is not None


def test_get_statement_report_for_empty_invoices(session):
    """Assert that the get statement report works for statement with no invoices."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment=payment, payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_payment_line_item(invoice_id=i.id, fee_schedule_id=1).save()

    settings_model = factory_statement_settings(payment_account_id=bcol_account.id,
                                                frequency=StatementFrequency.DAILY.value)
    statement_model = factory_statement(payment_account_id=bcol_account.id,
                                        frequency=StatementFrequency.DAILY.value,
                                        statement_settings_id=settings_model.id)

    payment_account = PaymentAccount.find_by_id(bcol_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None

    report_response, report_name = StatementService.get_statement_report(statement_id=statement_model.id,
                                                                         content_type='application/pdf',
                                                                         auth=get_auth_premium_user())
    assert report_response is not None


def test_get_weekly_statement_report(session):
    """Assert that the get statement report works."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment=payment, payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_payment_line_item(invoice_id=i.id, fee_schedule_id=1).save()

    settings_model = factory_statement_settings(payment_account_id=bcol_account.id,
                                                frequency=StatementFrequency.WEEKLY.value)
    statement_model = factory_statement(payment_account_id=bcol_account.id,
                                        frequency=StatementFrequency.WEEKLY.value,
                                        statement_settings_id=settings_model.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=i.id)

    payment_account = PaymentAccount.find_by_id(bcol_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None

    report_response, report_name = StatementService.get_statement_report(statement_id=statement_model.id,
                                                                         content_type='application/pdf',
                                                                         auth=get_auth_premium_user())
    assert report_response is not None
