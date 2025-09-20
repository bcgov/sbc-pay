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

"""Tests to assure the Statement Service.

Test-Suite to ensure that the Statement Service is working as expected.
"""
import pprint
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import ANY, patch

import pytz
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from pay_api.models import CorpType
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import DistributionCodeLink as DistributionCodeLinkModel
from pay_api.models import FeeCode
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import FilingType
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import StatementInvoices as StatementInvoiceModel
from pay_api.models import StatementSettings as StatementSettingsModel
from pay_api.services.payment_account import PaymentAccount as PaymentAccountService
from pay_api.services.report_service import ReportRequest, ReportService
from pay_api.services.statement import Statement as StatementService
from pay_api.utils.constants import DT_SHORT_FORMAT
from pay_api.utils.enums import ContentType, InvoiceStatus, PaymentMethod, StatementFrequency, StatementTemplate
from pay_api.utils.util import get_statement_date_string
from tests.utilities.base_test import (
    factory_eft_shortname,
    factory_eft_shortname_link,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_account,
    factory_payment_line_item,
    factory_premium_payment_account,
    factory_statement,
    factory_statement_invoices,
    factory_statement_settings,
    get_auth_premium_user,
    get_eft_enable_account_payload,
    get_premium_account_payload,
)


def test_statement_find_by_account(session):
    """Assert that the statement settings by id works."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=bcol_account, status_code=InvoiceStatus.OVERDUE.value)
    i.save()
    factory_invoice_reference(i.id).save()

    settings_model = factory_statement_settings(
        payment_account_id=bcol_account.id, frequency=StatementFrequency.DAILY.value
    )
    statement_model = factory_statement(
        payment_account_id=bcol_account.id,
        frequency=StatementFrequency.DAILY.value,
        statement_settings_id=settings_model.id,
    )
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=i.id)

    payment_account = PaymentAccountModel.find_by_id(bcol_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None
    assert statements.get("total") == 1
    assert statements.get("items")[0].get("is_overdue") is True


def test_get_statement_report(session):
    """Assert that the get statement report works."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_payment_line_item(invoice_id=i.id, fee_schedule_id=1).save()

    settings_model = factory_statement_settings(
        payment_account_id=bcol_account.id, frequency=StatementFrequency.DAILY.value
    )
    statement_model = factory_statement(
        payment_account_id=bcol_account.id,
        frequency=StatementFrequency.DAILY.value,
        statement_settings_id=settings_model.id,
    )
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=i.id)

    payment_account = PaymentAccountModel.find_by_id(bcol_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None

    report_response, report_name = StatementService.get_statement_report(
        statement_id=statement_model.id,
        content_type="application/pdf",
        auth=get_auth_premium_user(),
    )
    assert report_response is not None


def test_get_statement_report_for_empty_invoices(session):
    """Assert that the get statement report works for statement with no invoices."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_payment_line_item(invoice_id=i.id, fee_schedule_id=1).save()

    settings_model = factory_statement_settings(
        payment_account_id=bcol_account.id, frequency=StatementFrequency.DAILY.value
    )
    statement_model = factory_statement(
        payment_account_id=bcol_account.id,
        frequency=StatementFrequency.DAILY.value,
        statement_settings_id=settings_model.id,
    )

    payment_account = PaymentAccountModel.find_by_id(bcol_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None

    report_response, report_name = StatementService.get_statement_report(
        statement_id=statement_model.id,
        content_type="application/pdf",
        auth=get_auth_premium_user(),
    )
    assert report_response is not None


def test_get_weekly_statement_report(session):
    """Assert that the get statement report works."""
    bcol_account = factory_premium_payment_account()
    bcol_account.save()

    payment = factory_payment()
    payment.save()
    i = factory_invoice(payment_account=bcol_account)
    i.save()
    factory_invoice_reference(i.id).save()
    factory_payment_line_item(invoice_id=i.id, fee_schedule_id=1).save()

    settings_model = factory_statement_settings(
        payment_account_id=bcol_account.id, frequency=StatementFrequency.WEEKLY.value
    )
    statement_model = factory_statement(
        payment_account_id=bcol_account.id,
        frequency=StatementFrequency.WEEKLY.value,
        statement_settings_id=settings_model.id,
    )
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=i.id)

    payment_account = PaymentAccountModel.find_by_id(bcol_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None

    report_response, report_name = StatementService.get_statement_report(
        statement_id=statement_model.id,
        content_type="application/pdf",
        auth=get_auth_premium_user(),
    )
    assert report_response is not None


def test_get_weekly_interim_statement(session, admin_users_mock):
    """Assert that a weekly interim statement is generated."""
    account_create_date = datetime(2023, 10, 1, 12, 0)
    with freeze_time(account_create_date):
        account: PaymentAccountService = PaymentAccountService.create(
            get_premium_account_payload(payment_method=PaymentMethod.DRAWDOWN.value)
        )

        assert account is not None
        assert account.payment_method == PaymentMethod.DRAWDOWN.value

    # Assert that the default weekly statement settings are created
    statement_settings: StatementSettingsModel = StatementSettingsModel.find_active_settings(
        str(account.auth_account_id), datetime.now(tz=timezone.utc)
    )

    assert statement_settings is not None
    assert statement_settings.frequency == StatementFrequency.WEEKLY.value
    assert statement_settings.from_date == account_create_date.date()
    assert statement_settings.to_date is None

    # Setup previous payment method interim statement data
    invoice_create_date = localize_date(datetime(2023, 10, 9, 12, 0))
    weekly_invoice = factory_invoice(
        payment_account=account,
        created_on=invoice_create_date,
        payment_method_code=PaymentMethod.DRAWDOWN.value,
        status_code=InvoiceStatus.CREATED.value,
        total=50,
    ).save()

    assert weekly_invoice is not None
    update_date = localize_date(datetime(2023, 10, 12, 12, 0))
    with freeze_time(update_date):
        account = PaymentAccountService.update(
            account.auth_account_id,
            get_eft_enable_account_payload(
                payment_method=PaymentMethod.EFT.value,
                account_id=account.auth_account_id,
            ),
        )

        new_statement_settings: StatementSettingsModel = StatementSettingsModel.find_latest_settings(
            account.auth_account_id
        )

        assert new_statement_settings is not None
        assert new_statement_settings.id != statement_settings.id
        assert new_statement_settings.frequency == StatementFrequency.MONTHLY.value
        assert new_statement_settings.to_date is None

    # Validate interim statement has the correct invoice
    statements = StatementService.get_account_statements(auth_account_id=account.auth_account_id, page=1, limit=100)

    assert statements is not None
    assert len(statements[0]) == 1
    assert statements[0][0].is_interim_statement

    # Validate weekly interim invoice is correct
    weekly_invoices = StatementInvoiceModel.find_all_invoices_for_statement(statements[0][0].id)
    assert weekly_invoices is not None
    assert len(weekly_invoices) == 1
    assert weekly_invoices[0].invoice_id == weekly_invoice.id


def test_get_interim_statement_change_away_from_eft(session, admin_users_mock):
    """Assert that a payment method update interim statement is generated."""
    account_create_date = datetime(2023, 10, 1, 12, 0)
    with freeze_time(account_create_date):
        account: PaymentAccountService = PaymentAccountService.create(
            get_eft_enable_account_payload(payment_method=PaymentMethod.EFT.value)
        )

        assert account is not None
        assert account.payment_method == PaymentMethod.EFT.value

    # Assert that the default MONTHLY statement settings are created
    statement_settings: StatementSettingsModel = StatementSettingsModel.find_active_settings(
        str(account.auth_account_id), datetime.now(tz=timezone.utc)
    )

    assert statement_settings is not None
    assert statement_settings.frequency == StatementFrequency.MONTHLY.value
    assert statement_settings.from_date == account_create_date.date()
    assert statement_settings.to_date is None

    # Setup previous payment method interim statement data
    invoice_create_date = localize_date(datetime(2023, 10, 9, 12, 0))
    monthly_invoice = factory_invoice(
        payment_account=account,
        created_on=invoice_create_date,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.PAID.value,
        total=50,
        paid=50,
    ).save()

    assert monthly_invoice is not None
    update_date = localize_date(datetime(2023, 10, 12, 12, 0))
    with freeze_time(update_date):
        account = PaymentAccountService.update(
            account.auth_account_id,
            get_premium_account_payload(
                payment_method=PaymentMethod.DRAWDOWN.value,
                account_id=account.auth_account_id,
            ),
        )

        new_statement_settings: StatementSettingsModel = StatementSettingsModel.find_latest_settings(
            account.auth_account_id
        )

        assert new_statement_settings is not None
        assert new_statement_settings.id != statement_settings.id
        assert new_statement_settings.to_date is None

    # Validate interim statement has the correct invoice
    statements = StatementService.get_account_statements(auth_account_id=account.auth_account_id, page=1, limit=100)

    assert statements is not None
    assert len(statements[0]) == 1
    assert statements[0][0].is_interim_statement
    assert statements[0][0].payment_methods == PaymentMethod.EFT.value

    # Validate interim invoice is correct
    interim_invoices = StatementInvoiceModel.find_all_invoices_for_statement(statements[0][0].id)
    assert interim_invoices is not None
    assert len(interim_invoices) == 1
    assert interim_invoices[0].invoice_id == monthly_invoice.id


def test_get_monthly_interim_statement(session, admin_users_mock):
    """Assert that a monthly interim statement is generated."""
    account_create_date = datetime(2023, 10, 1, 12, 0)
    with freeze_time(account_create_date):
        account: PaymentAccountService = PaymentAccountService.create(
            get_premium_account_payload(payment_method=PaymentMethod.DRAWDOWN.value)
        )

        assert account is not None
        assert account.payment_method == PaymentMethod.DRAWDOWN.value

    # Update current active settings to monthly
    statement_settings: StatementSettingsModel = StatementSettingsModel.find_active_settings(
        str(account.auth_account_id), datetime.now(tz=timezone.utc)
    )

    statement_settings.frequency = StatementFrequency.MONTHLY.value
    statement_settings.save()

    assert statement_settings is not None
    assert statement_settings.frequency == StatementFrequency.MONTHLY.value
    assert statement_settings.from_date == account_create_date.date()
    assert statement_settings.to_date is None

    # Setup previous payment method interim statement data
    invoice_create_date = localize_date(datetime(2023, 10, 9, 12, 0))
    monthly_invoice = factory_invoice(
        payment_account=account,
        created_on=invoice_create_date,
        payment_method_code=PaymentMethod.DRAWDOWN.value,
        status_code=InvoiceStatus.CREATED.value,
        total=50,
    ).save()

    assert monthly_invoice is not None

    update_date = localize_date(datetime(2023, 10, 12, 12, 0))
    with freeze_time(update_date):
        account = PaymentAccountService.update(
            account.auth_account_id,
            get_eft_enable_account_payload(
                payment_method=PaymentMethod.EFT.value,
                account_id=account.auth_account_id,
            ),
        )

        new_statement_settings: StatementSettingsModel = StatementSettingsModel.find_latest_settings(
            account.auth_account_id
        )

        assert new_statement_settings is not None
        assert new_statement_settings.id != statement_settings.id
        assert new_statement_settings.frequency == StatementFrequency.MONTHLY.value
        assert new_statement_settings.to_date is None

    # Validate interim statement has the correct invoice
    statements = StatementService.get_account_statements(auth_account_id=account.auth_account_id, page=1, limit=100)

    assert statements is not None
    assert len(statements[0]) == 1
    assert statements[0][0].is_interim_statement

    # Validate monthly interim invoice is correct
    monthly_invoices = StatementInvoiceModel.find_all_invoices_for_statement(statements[0][0].id)
    assert monthly_invoices is not None
    assert len(monthly_invoices) == 1
    assert monthly_invoices[0].invoice_id == monthly_invoice.id


def test_interim_statement_settings_eft(db, session, admin_users_mock):
    """Assert statement setting properly generated when transitioning to and from EFT payment method."""
    account_create_date = datetime(2024, 5, 30, 12, 0)
    with freeze_time(account_create_date):
        account: PaymentAccountService = PaymentAccountService.create(
            get_premium_account_payload(payment_method=PaymentMethod.DRAWDOWN.value)
        )

        assert account is not None
        assert account.payment_method == PaymentMethod.DRAWDOWN.value

    # Confirm initial default settings when account is created
    initial_settings: StatementSettingsModel = StatementSettingsModel.find_active_settings(
        str(account.auth_account_id), datetime.now(tz=timezone.utc)
    )

    assert initial_settings is not None
    assert initial_settings.frequency == StatementFrequency.WEEKLY.value
    assert initial_settings.from_date == account_create_date.date()
    assert initial_settings.to_date is None

    update_date = localize_date(datetime(2024, 6, 13, 12, 0))
    with freeze_time(update_date):
        account = PaymentAccountService.update(
            account.auth_account_id,
            get_eft_enable_account_payload(
                payment_method=PaymentMethod.EFT.value,
                account_id=account.auth_account_id,
            ),
        )
    # Assert initial settings are properly end dated
    assert initial_settings is not None
    assert initial_settings.frequency == StatementFrequency.WEEKLY.value
    assert initial_settings.from_date == account_create_date.date()
    assert initial_settings.to_date == update_date.date()

    # Assert new EFT Monthly settings are created
    latest_statement_settings: StatementSettingsModel = StatementSettingsModel.find_latest_settings(
        account.auth_account_id
    )

    assert latest_statement_settings is not None
    assert latest_statement_settings.id != initial_settings.id
    assert latest_statement_settings.frequency == StatementFrequency.MONTHLY.value
    assert latest_statement_settings.from_date == (update_date + timedelta(days=1)).date()
    assert latest_statement_settings.to_date is None

    # Same day payment method change back to DRAWDOWN
    update_date = localize_date(datetime(2024, 6, 13, 12, 5))
    with freeze_time(update_date):
        account = PaymentAccountService.update(
            account.auth_account_id,
            get_premium_account_payload(payment_method=PaymentMethod.DRAWDOWN.value),
        )

    latest_statement_settings: StatementSettingsModel = StatementSettingsModel.find_latest_settings(
        account.auth_account_id
    )

    assert latest_statement_settings is not None
    assert latest_statement_settings.id != initial_settings.id
    assert latest_statement_settings.frequency == StatementFrequency.WEEKLY.value
    assert latest_statement_settings.from_date == (update_date + timedelta(days=1)).date()
    assert latest_statement_settings.to_date is None

    # Same day payment method change back to EFT
    update_date = localize_date(datetime(2024, 6, 13, 12, 6))
    with freeze_time(update_date):
        account = PaymentAccountService.update(
            account.auth_account_id,
            get_eft_enable_account_payload(
                payment_method=PaymentMethod.EFT.value,
                account_id=account.auth_account_id,
            ),
        )

    latest_statement_settings: StatementSettingsModel = StatementSettingsModel.find_latest_settings(
        account.auth_account_id
    )

    assert latest_statement_settings is not None
    assert latest_statement_settings.id != initial_settings.id
    assert latest_statement_settings.frequency == StatementFrequency.MONTHLY.value
    assert latest_statement_settings.from_date == (update_date + timedelta(days=1)).date()
    assert latest_statement_settings.to_date is None

    all_settings = (
        db.session.query(StatementSettingsModel)
        .filter(StatementSettingsModel.payment_account_id == account.id)
        .order_by(StatementSettingsModel.id)
    ).all()

    assert all_settings is not None
    assert len(all_settings) == 2

    expected_from_date = latest_statement_settings.from_date

    # Change payment method to DRAWDOWN 1 day later - should create a new statement settings record
    update_date = localize_date(datetime(2024, 6, 14, 12, 6))
    with freeze_time(update_date):
        account = PaymentAccountService.update(
            account.auth_account_id,
            get_premium_account_payload(payment_method=PaymentMethod.DRAWDOWN.value),
        )

    latest_statement_settings: StatementSettingsModel = StatementSettingsModel.find_latest_settings(
        account.auth_account_id
    )

    assert latest_statement_settings is not None
    assert latest_statement_settings.id != initial_settings.id
    assert latest_statement_settings.frequency == StatementFrequency.WEEKLY.value
    assert latest_statement_settings.from_date == (update_date + timedelta(days=1)).date()
    assert latest_statement_settings.to_date is None

    all_settings = (
        db.session.query(StatementSettingsModel)
        .filter(StatementSettingsModel.payment_account_id == account.id)
        .order_by(StatementSettingsModel.id)
    ).all()

    assert all_settings is not None
    assert len(all_settings) == 3

    # Assert previous settings properly end dated
    assert all_settings[1].frequency == StatementFrequency.MONTHLY.value
    assert all_settings[1].from_date == expected_from_date
    assert all_settings[1].to_date == update_date.date()


def test_get_eft_statement_for_empty_invoices(session):
    """Assert that the get statement report works for eft statement with no invoices."""
    statement_from_date = datetime.now(timezone.utc) + relativedelta(months=1, day=1)
    statement_to_date = statement_from_date + relativedelta(months=1, days=-1)
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value)
    settings_model = factory_statement_settings(
        payment_account_id=payment_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        from_date=statement_from_date,
    )
    statement_model = factory_statement(
        payment_account_id=payment_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=settings_model.id,
        from_date=statement_from_date,
        to_date=statement_to_date,
    )

    payment_account = PaymentAccountModel.find_by_id(payment_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None
    expected_report_name = (
        f"bcregistry-statements-{statement_from_date.strftime(DT_SHORT_FORMAT)}-"
        f"to-{statement_to_date.strftime(DT_SHORT_FORMAT)}.pdf"
    )
    with patch.object(ReportService, "get_report_response", return_value=None) as mock_report:
        report_response, report_name = StatementService.get_statement_report(
            statement_id=statement_model.id,
            content_type=ContentType.PDF.value,
            auth=get_auth_premium_user(),
        )
        assert report_name == expected_report_name

        date_string_now = get_statement_date_string(datetime.now(tz=timezone.utc))
        expected_template_vars = {
            "account": {
                "accountType": "PREMIUM",
                "contact": {
                    "city": "Westbank",
                    "country": "CA",
                    "created": "2020-05-14T17:33:04.315908+00:00",
                    "createdBy": "BCREGTEST Bena THIRTEEN",
                    "modified": "2020-08-07T23:55:56.576008+00:00",
                    "modifiedBy": "BCREGTEST Bena THIRTEEN",
                    "postalCode": "V4T 2A5",
                    "region": "BC",
                    "street": "66-2098 Boucherie Rd",
                    "streetAdditional": "First",
                },
                "id": "1234",
                "name": "Mock Account",
                "paymentPreference": {
                    "bcOnlineAccountId": "1234567890",
                    "bcOnlineUserId": "PB25020",
                    "methodOfPayment": "DRAWDOWN",
                },
            },
            "groupedInvoices": [],
            "statement": {
                "amount_owing": "0.00",
                "created_on": date_string_now,
                "frequency": "MONTHLY",
                "from_date": get_statement_date_string(statement_from_date),
                "to_date": get_statement_date_string(statement_to_date),
                "id": statement_model.id,
                "is_interim_statement": False,
                "is_overdue": False,
                "notification_date": None,
                "overdue_notification_date": None,
                "payment_methods": ["EFT"],
                "statement_total": 0.0,
                "duration": (
                    f"{get_statement_date_string(statement_from_date)} - "
                    f"{get_statement_date_string(statement_to_date)}"
                ),
            },
            "statementSummary": {
                "dueDate": get_statement_date_string(
                    StatementService.calculate_due_date(statement_to_date.date())
                ),  # pylint: disable=protected-access
                "lastStatementTotal": "0.00",
                "lastStatementPaidAmount": "0.00",
                "latestStatementPaymentDate": None,
            },
            "total": {
                "due": "0.00",
                "fees": "0.00",
                "paid": "0.00",
                "serviceFees": "0.00",
                "statutoryFees": "0.00",
            },
            "summaryPage": {"display_summary_page": False},
        }
        expected_report_inputs = ReportRequest(
            report_name=report_name,
            template_name=StatementTemplate.STATEMENT_REPORT.value,
            template_vars=expected_template_vars,
            populate_page_number=True,
            content_type=ContentType.PDF.value,
        )
        mock_report.assert_called_with(expected_report_inputs)


def test_get_eft_statement_with_invoices(session):
    """Assert that the get statement report works for eft statement with invoices."""
    statement_from_date = datetime.now(tz=timezone.utc) + relativedelta(months=1, day=1)
    statement_to_date = statement_from_date + relativedelta(months=1, days=-1)
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value)
    settings_model = factory_statement_settings(
        payment_account_id=payment_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        from_date=statement_from_date,
    )
    statement_model = factory_statement(
        payment_account_id=payment_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=settings_model.id,
        from_date=statement_from_date,
        to_date=statement_to_date,
    )

    payment_account = PaymentAccountModel.find_by_id(payment_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None

    invoice_1 = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=200,
        paid=0,
    ).save()
    factory_payment_line_item(invoice_id=invoice_1.id, fee_schedule_id=1).save()
    invoice_2 = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=50,
        paid=0,
    ).save()
    factory_payment_line_item(invoice_id=invoice_2.id, fee_schedule_id=1).save()

    invoice_3 = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.PAID.value,
        total=50,
        paid=50,
        payment_date=datetime.now(tz=timezone.utc) + timedelta(days=9000),
    ).save()
    factory_payment_line_item(invoice_id=invoice_3.id, fee_schedule_id=1).save()

    invoice_4 = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.PAID.value,
        total=50,
        paid=50,
        payment_date=statement_model.from_date + timedelta(days=1),
    ).save()
    factory_payment_line_item(invoice_id=invoice_4.id, fee_schedule_id=1).save()

    # Create fee schedule with GST enabled for invoice 5
    fee_code_gst = FeeCode(code="GSTFEE", amount=Decimal("100.00"))
    fee_code_gst.save()

    service_fee_code_gst = FeeCode(code="GSTSRV", amount=Decimal("25.00"))
    service_fee_code_gst.save()

    corp_type_gst = CorpType(code="GSTTEST", description="GST Test Corp", product="BUSINESS")
    corp_type_gst.save()

    filing_type_gst = FilingType(code="GSTTEST", description="GST Test Filing")
    filing_type_gst.save()

    fee_schedule_gst = FeeScheduleModel(
        filing_type_code="GSTTEST",
        corp_type_code="GSTTEST",
        fee_code="GSTFEE",
        fee_start_date=datetime.now(tz=timezone.utc).date(),
        gst_added=True,
        show_on_pricelist=True,
        service_fee=service_fee_code_gst,
    )
    fee_schedule_gst.save()

    # Create distribution code for the GST fee schedule
    distribution_code_gst = DistributionCodeModel(
        name="GST Test Distribution Code",
        client="100",
        responsibility_centre="22222",
        service_line="33333",
        stob="4444",
        project_code="5555555",
        start_date=datetime.now(tz=timezone.utc).date(),
        created_by="test",
    )
    distribution_code_gst.save()

    # Link distribution code to fee schedule
    DistributionCodeLinkModel(
        fee_schedule_id=fee_schedule_gst.fee_schedule_id,
        distribution_code_id=distribution_code_gst.distribution_code_id,
    ).save()

    # Create invoice with GST (including service fee GST and statutory fee GST)
    invoice_5 = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=150,
        paid=0,
    ).save()
    factory_payment_line_item(
        invoice_id=invoice_5.id,
        fee_schedule_id=fee_schedule_gst.fee_schedule_id,
        service_fees=25.0,
        total=150.0,
        service_fees_gst=1.25,
        statutory_fees_gst=5.0,
    ).save()

    # Update the invoice to include service fees and GST
    invoice_5.service_fees = Decimal("25.00")
    invoice_5.gst = Decimal("6.25")
    invoice_5.save()

    factory_invoice_reference(invoice_1.id).save()
    factory_invoice_reference(invoice_2.id).save()
    factory_invoice_reference(invoice_3.id).save()
    factory_invoice_reference(invoice_4.id).save()
    factory_invoice_reference(invoice_5.id).save()

    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice_1.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice_2.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice_3.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice_4.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=invoice_5.id)
    expected_report_name = (
        f"bcregistry-statements-{statement_from_date.strftime(DT_SHORT_FORMAT)}-"
        f"to-{statement_to_date.strftime(DT_SHORT_FORMAT)}.pdf"
    )
    with patch.object(ReportService, "get_report_response", return_value=None) as mock_report:
        report_response, report_name = StatementService.get_statement_report(
            statement_id=statement_model.id,
            content_type=ContentType.PDF.value,
            auth=get_auth_premium_user(),
        )

        assert report_name == expected_report_name

        date_string_now = get_statement_date_string(datetime.now(tz=timezone.utc))
        expected_template_vars = {
            "account": {
                "accountType": "PREMIUM",
                "contact": {
                    "city": "Westbank",
                    "country": "CA",
                    "created": "2020-05-14T17:33:04.315908+00:00",
                    "createdBy": "BCREGTEST Bena THIRTEEN",
                    "modified": "2020-08-07T23:55:56.576008+00:00",
                    "modifiedBy": "BCREGTEST Bena THIRTEEN",
                    "postalCode": "V4T 2A5",
                    "region": "BC",
                    "street": "66-2098 Boucherie Rd",
                    "streetAdditional": "First",
                },
                "id": payment_account.auth_account_id,
                "name": "Mock Account",
                "paymentPreference": {
                    "bcOnlineAccountId": "1234567890",
                    "bcOnlineUserId": "PB25020",
                    "methodOfPayment": "DRAWDOWN",
                },
            },
            "groupedInvoices": [
                {
                    "amount_owing": "400.00",
                    "credits_total": 0.0,
                    "due_date": get_statement_date_string(
                        StatementService.calculate_due_date(statement_to_date.date())
                    ),  # pylint: disable=protected-access
                    "due_summary": 450.0,
                    "fees_total": 468.75,
                    "gst_total": 6.25,
                    "include_service_provided": True,
                    "is_index_0": True,
                    "paid_summary": 50.0,
                    "payment_method": "EFT",
                    "refunds_total": 0.0,
                    "service_fees_total": 25.0,
                    "statement_header_text": "ACCOUNT STATEMENT - ELECTRONIC FUNDS TRANSFER",
                    "total_paid": "100.00",
                    "totals_summary": 500.0,
                    "transactions": [
                        {
                            "bcol_account": "TEST",
                            "business_identifier": "CP0001234",
                            "corp_type_code": "CP",
                            "created_by": "test",
                            "created_name": "test name",
                            "created_on": ANY,
                            "details": ["label value"],
                            "fee": "200.00",
                            "folio": "1234567890",
                            "gst": "0.00",
                            "id": invoice_1.id,
                            "invoice_number": "10021",
                            "line_items": [
                                {
                                    "description": "test",
                                    "filing_type_code": "OTANN",
                                    "gst": 0.0,
                                    "pst": 0.0,
                                    "service_fees": 0.0,
                                    "total": 10.0,
                                },
                            ],
                            "paid": 0.0,
                            "payment_account": {
                                "account_id": "1234",
                                "billable": True,
                            },
                            "payment_method": "EFT",
                            "product": "BUSINESS",
                            "products": ["test"],
                            "refund": 0.0,
                            "service_fee": "0.00",
                            "service_provided": False,
                            "status_code": "Invoice Approved",
                            "total": "200.00",
                        },
                        {
                            "bcol_account": "TEST",
                            "business_identifier": "CP0001234",
                            "corp_type_code": "CP",
                            "created_by": "test",
                            "created_name": "test name",
                            "created_on": ANY,
                            "details": ["label value"],
                            "fee": "50.00",
                            "folio": "1234567890",
                            "gst": "0.00",
                            "id": invoice_2.id,
                            "invoice_number": "10021",
                            "line_items": [
                                {
                                    "description": "test",
                                    "filing_type_code": "OTANN",
                                    "gst": 0.0,
                                    "pst": 0.0,
                                    "service_fees": 0.0,
                                    "total": 10.0,
                                },
                            ],
                            "paid": 0.0,
                            "payment_account": {"account_id": "1234", "billable": True},
                            "payment_method": "EFT",
                            "product": "BUSINESS",
                            "products": ["test"],
                            "refund": 0.0,
                            "service_fee": "0.00",
                            "service_provided": False,
                            "status_code": "Invoice Approved",
                            "total": "50.00",
                        },
                        {
                            "bcol_account": "TEST",
                            "business_identifier": "CP0001234",
                            "corp_type_code": "CP",
                            "created_by": "test",
                            "created_name": "test name",
                            "created_on": ANY,
                            "details": ["label value"],
                            "fee": "50.00",
                            "folio": "1234567890",
                            "gst": "0.00",
                            "id": invoice_3.id,
                            "invoice_number": "10021",
                            "line_items": [
                                {
                                    "description": "test",
                                    "filing_type_code": "OTANN",
                                    "gst": 0.0,
                                    "pst": 0.0,
                                    "service_fees": 0.0,
                                    "total": 10.0,
                                },
                            ],
                            "paid": 50.0,
                            "payment_account": {"account_id": "1234", "billable": True},
                            "payment_date": datetime.strftime(invoice_3.payment_date, "%Y-%m-%dT%H:%M:%S.%f"),
                            "payment_method": "EFT",
                            "product": "BUSINESS",
                            "products": ["test"],
                            "refund": 0.0,
                            "service_fee": "0.00",
                            "service_provided": True,
                            "status_code": "COMPLETED",
                            "total": "50.00",
                        },
                        {
                            "bcol_account": "TEST",
                            "business_identifier": "CP0001234",
                            "corp_type_code": "CP",
                            "created_by": "test",
                            "created_name": "test name",
                            "created_on": ANY,
                            "details": ["label value"],
                            "fee": "50.00",
                            "folio": "1234567890",
                            "gst": "0.00",
                            "id": invoice_4.id,
                            "invoice_number": "10021",
                            "line_items": [
                                {
                                    "description": "test",
                                    "filing_type_code": "OTANN",
                                    "gst": 0.0,
                                    "pst": 0.0,
                                    "service_fees": 0.0,
                                    "total": 10.0,
                                },
                            ],
                            "paid": 50.0,
                            "payment_account": {"account_id": "1234", "billable": True},
                            "payment_date": datetime.strftime(invoice_4.payment_date, "%Y-%m-%dT%H:%M:%S"),
                            "payment_method": "EFT",
                            "product": "BUSINESS",
                            "products": ["test"],
                            "refund": 0.0,
                            "service_fee": "0.00",
                            "service_provided": True,
                            "status_code": "COMPLETED",
                            "total": "50.00",
                        },
                        {
                            "bcol_account": "TEST",
                            "business_identifier": "CP0001234",
                            "corp_type_code": "CP",
                            "created_by": "test",
                            "created_name": "test name",
                            "created_on": ANY,
                            "details": ["label value"],
                            "fee": "118.75",
                            "folio": "1234567890",
                            "gst": "6.25",
                            "id": invoice_5.id,
                            "invoice_number": "10021",
                            "line_items": [
                                {
                                    "description": "test",
                                    "filing_type_code": "GSTTEST",
                                    "gst": 6.25,
                                    "pst": 0.0,
                                    "service_fees": 25.0,
                                    "service_fees_gst": 1.25,
                                    "statutory_fees_gst": 5.0,
                                    "total": 150.0,
                                },
                            ],
                            "paid": 0.0,
                            "payment_account": {"account_id": "1234", "billable": True},
                            "payment_method": "EFT",
                            "product": "BUSINESS",
                            "products": ["test"],
                            "refund": 0.0,
                            "service_fee": "25.00",
                            "service_provided": False,
                            "status_code": "Invoice Approved",
                            "total": "150.00",
                        },
                    ],
                }
            ],
            "statement": {
                "amount_owing": "400.00",
                "created_on": date_string_now,
                "duration": (
                    f"{get_statement_date_string(statement_from_date)} - "
                    f"{get_statement_date_string(statement_to_date)}"
                ),
                "frequency": "MONTHLY",
                "from_date": get_statement_date_string(statement_from_date),
                "to_date": get_statement_date_string(statement_to_date),
                "id": statement_model.id,
                "is_interim_statement": False,
                "is_overdue": False,
                "notification_date": None,
                "overdue_notification_date": None,
                "payment_methods": ["EFT"],
                "statement_total": 500.0,
            },
            "statementSummary": {
                "dueDate": get_statement_date_string(
                    StatementService.calculate_due_date(statement_to_date.date())
                ),  # pylint: disable=protected-access
                "lastStatementTotal": "0.00",
                "lastStatementPaidAmount": "0.00",
                "latestStatementPaymentDate": get_statement_date_string(invoice_3.payment_date.strftime("%Y-%m-%d")),
            },
            # 2 are paid - looking with reference to the "statement", 1 is paid ($50) within the statement period
            "total": {
                "due": "450.00",
                "fees": "500.00",
                "paid": "50.00",
                "serviceFees": "25.00",
                "statutoryFees": "475.00",
            },
            "summaryPage": {"display_summary_page": False},
            "hasPaymentInstructions": True,
        }
        expected_report_inputs = ReportRequest(
            report_name=report_name,
            template_name=StatementTemplate.STATEMENT_REPORT.value,
            template_vars=expected_template_vars,
            populate_page_number=True,
            content_type=ContentType.PDF.value,
        )

        mock_report.assert_called_with(expected_report_inputs)


def test_summary_page_with_invoices(session):
    """Assert that the summary page toggles on when multiple payment methods (PAD, CC) are present."""
    statement_from_date = datetime.now(tz=timezone.utc) + relativedelta(months=1, day=1)
    statement_to_date = statement_from_date + relativedelta(months=1, days=-1)
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.DRAWDOWN.value)
    settings_model = factory_statement_settings(
        payment_account_id=payment_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        from_date=statement_from_date,
    )
    statement_model = factory_statement(
        payment_account_id=payment_account.id,
        frequency=StatementFrequency.MONTHLY.value,
        statement_settings_id=settings_model.id,
        from_date=statement_from_date,
        to_date=statement_to_date,
    )

    payment_account = PaymentAccountModel.find_by_id(payment_account.id)
    statements = StatementService.find_by_account_id(payment_account.auth_account_id, page=1, limit=10)
    assert statements is not None

    inv_pad = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.PAD.value,
        status_code=InvoiceStatus.APPROVED.value,
        total=120,
        paid=20,
    ).save()
    factory_payment_line_item(invoice_id=inv_pad.id, fee_schedule_id=1).save()

    inv_cc = factory_invoice(
        payment_account,
        payment_method_code=PaymentMethod.CC.value,
        status_code=InvoiceStatus.PAID.value,
        total=80,
        paid=80,
    ).save()
    factory_payment_line_item(invoice_id=inv_cc.id, fee_schedule_id=1).save()

    factory_invoice_reference(inv_pad.id).save()
    factory_invoice_reference(inv_cc.id).save()

    factory_statement_invoices(statement_id=statement_model.id, invoice_id=inv_pad.id)
    factory_statement_invoices(statement_id=statement_model.id, invoice_id=inv_cc.id)

    with patch.object(ReportService, "get_report_response", return_value=None) as mock_report:
        report_response, report_name = StatementService.get_statement_report(
            statement_id=statement_model.id,
            content_type=ContentType.PDF.value,
            auth=get_auth_premium_user(),
        )

        args, kwargs = mock_report.call_args
        req: ReportRequest = args[0]
        tmpl = req.template_vars

        assert "summaryPage" in tmpl
        assert tmpl["summaryPage"]["display_summary_page"] is True
        grouped_summary = tmpl["summaryPage"].get("grouped_summary", [])
        methods = {row.get("payment_method") for row in grouped_summary}
        assert methods == {"Pre Authorized Debit", "Credit Card"}


def localize_date(date: datetime):
    """Localize date object by adding timezone information."""
    pst = pytz.timezone("America/Vancouver")
    return pst.localize(date)


def test_get_eft_statement_summary_links_count(session):
    """Assert that the get statement summary short name links count is correct."""
    payment_account = factory_payment_account(payment_method_code=PaymentMethod.EFT.value)
    summary = StatementService.get_summary(payment_account.auth_account_id)
    assert summary["short_name_links_count"] == 0

    eft_short_name = factory_eft_shortname("TESTSHORTNAME")
    eft_short_name.save()

    factory_eft_shortname_link(short_name_id=eft_short_name.id, auth_account_id=payment_account.auth_account_id).save()

    summary = StatementService.get_summary(payment_account.auth_account_id)
    assert summary["short_name_links_count"] == 1

    factory_eft_shortname_link(short_name_id=eft_short_name.id, auth_account_id="2222").save()

    summary = StatementService.get_summary(payment_account.auth_account_id)
    assert summary["short_name_links_count"] == 2
