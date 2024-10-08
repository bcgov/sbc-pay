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

"""Tests to assure the CorpType Class.

Test-Suite to ensure that the CorpType Class is working as expected.
"""
from datetime import datetime, timezone

import pytest
from dateutil.relativedelta import relativedelta

from pay_api.models import Invoice, InvoiceSchema
from pay_api.utils.enums import CorpType, InvoiceStatus, PaymentMethod
from tests.utilities.base_test import factory_invoice, factory_payment, factory_payment_account


def test_invoice(session):
    """Assert a invoice is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account=payment_account)
    invoice.save()
    assert invoice.id is not None

    # assert overdue default is set
    assert invoice.overdue_date is not None
    assert invoice.overdue_date.date() == (datetime.now(tz=timezone.utc) + relativedelta(months=2, day=15)).date()


def test_invoice_find_by_id(session):
    """Assert a invoice is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account=payment_account)
    invoice.save()
    assert invoice.find_by_id(invoice.id) is not None
    schema = InvoiceSchema()
    d = schema.dump(invoice)
    assert d.get("id") == invoice.id


def test_payments_marked_for_delete(session):
    """Assert a payment is stored.

    Start with a blank database.
    """
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(status_code=InvoiceStatus.DELETE_ACCEPTED.value, payment_account=payment_account)
    # invoice.invoice_status_code == InvoiceStatus.DELETE_ACCEPTED.value
    invoice.save()
    invoices = Invoice.find_invoices_marked_for_delete()
    assert len(invoices) == 1


@pytest.mark.parametrize(
    "test_name, created_on, overdue_date",
    [
        ("March - PDT - edge", datetime(2024, 1, 1, 8), datetime(2024, 3, 15, 7, 0, 0)),
        ("April - PDT - edge", datetime(2024, 2, 1, 8), datetime(2024, 4, 15, 7, 0, 0)),
        (
            "November - PST - edge",
            datetime(2024, 9, 1, 8),
            datetime(2024, 11, 15, 8, 0, 0),
        ),
        (
            "December - PST - edge",
            datetime(2024, 10, 1, 8),
            datetime(2024, 12, 15, 8, 0, 0),
        ),
        (
            "End of the month invoice creation",
            datetime(2024, 1, 31, 8),
            datetime(2024, 3, 15, 7, 0, 0),
        ),
        (
            "Beginning of month invoice creation",
            datetime(2023, 12, 1, 8),
            datetime(2024, 2, 15, 8, 0, 0),
        ),
    ],
)
def test_overdue_date(session, test_name, created_on, overdue_date):
    """Test overdue date to make sure it's right TZ."""
    # PDT -> PST on Nov 3, 2024 at 2:00 am
    # PST -> PDT on March 10, 2024 at 2:00 am
    invoice = factory_invoice(created_on=created_on, payment_account=factory_payment_account())
    invoice.save()
    assert invoice.overdue_date == overdue_date


def test_invoice_created_on(session):
    """Assert a invoice created_on isn't the same for two invoices."""
    payment_account = factory_payment_account()
    dates = []
    for _ in range(2):
        invoice = Invoice(
            invoice_status_code=InvoiceStatus.CREATED.value,
            payment_account_id=payment_account.id,
            total=0,
            paid=0,
            created_by="test",
            created_name="hey",
            business_identifier=None,
            corp_type_code=CorpType.VS.value,
            folio_number=None,
            service_fees=0,
            bcol_account=payment_account.bcol_account,
            payment_method_code=PaymentMethod.DIRECT_PAY.value,
            routing_slip=None,
            details=[],
        )
        invoice.save()
        dates.append(invoice.created_on)
    assert dates[0] != dates[1]
