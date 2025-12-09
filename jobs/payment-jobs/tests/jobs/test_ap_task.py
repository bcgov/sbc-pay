# Copyright © 2023 Province of British Columbia
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

"""Tests to assure the CGI AP Job.

Test-Suite to ensure that the AP Refund Job is working as expected.
"""

import re
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import RoutingSlip
from pay_api.utils.enums import (
    APRefundMethod,
    CfsAccountStatus,
    DisbursementStatus,
    EFTShortnameRefundStatus,
    InvoiceStatus,
    PaymentMethod,
    RoutingSlipStatus,
)
from tasks.ap_task import ApTask
from tasks.common.cgi_ap import CgiAP
from tasks.common.dataclasses import APFlow, APHeader, APLine, APSupplier

from .factory import (
    factory_create_eft_account,
    factory_create_eft_credit,
    factory_create_eft_credit_invoice_link,
    factory_create_eft_file,
    factory_create_eft_refund,
    factory_create_eft_shortname,
    factory_create_eft_transaction,
    factory_create_pad_account,
    factory_eft_shortname_link,
    factory_invoice,
    factory_payment_line_item,
    factory_refund,
    factory_routing_slip_account,
)


def test_eft_refunds(session, monkeypatch):
    """Test EFT AP refund job.

    Steps:
    1) Create an invoice with refund and status REFUNDED
    2) Run the job and assert status
    """
    account = factory_create_eft_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    invoice = factory_invoice(
        payment_account=account,
        payment_method_code=PaymentMethod.EFT.value,
        status_code=InvoiceStatus.PAID.value,
        total=100,
    )
    short_name = factory_create_eft_shortname("SHORTNAMETEST")
    eft_refund = factory_create_eft_refund(
        disbursement_status_code=None,
        refund_amount=100,
        refund_email="test@test.com",
        short_name_id=short_name.id,
        status=EFTShortnameRefundStatus.APPROVED.value,
        refund_method=APRefundMethod.EFT.value,
    )
    eft_refund.save()
    eft_file = factory_create_eft_file()
    eft_transaction = factory_create_eft_transaction(file_id=eft_file.id)
    eft_credit = factory_create_eft_credit(
        short_name_id=short_name.id,
        eft_transaction_id=eft_transaction.id,
        eft_file_id=eft_file.id,
    )
    eft_refund_cheque = factory_create_eft_refund(
        disbursement_status_code=None,
        refund_amount=100,
        refund_email="test@test.com",
        short_name_id=short_name.id,
        status=EFTShortnameRefundStatus.APPROVED.value,
        refund_method=APRefundMethod.CHEQUE.value,
        city="Victoria",
        region="BC",
        street="655 Douglas St",
        country="CA",
        postal_code="V8V 0B6",
        entity_name="TEST",
    )
    eft_refund_cheque.save()
    factory_create_eft_credit_invoice_link(invoice_id=invoice.id, eft_credit_id=eft_credit.id)
    factory_eft_shortname_link(short_name_id=short_name.id)

    with patch("tasks.common.cgi_ejv.CgiEjv.upload") as mock_upload:
        ApTask.create_ap_files()
        mock_upload.assert_called()


def test_routing_slip_refunds(session, monkeypatch):
    """Test Routing slip AP refund job.

    Steps:
    1) Create a routing slip with remaining_amount and status REFUND_AUTHORIZED
    2) Run the job and assert status
    """
    rs_1 = "RS0000001"
    factory_routing_slip_account(
        number=rs_1,
        status=CfsAccountStatus.ACTIVE.value,
        total=100,
        remaining_amount=0,
        auth_account_id="1234",
        routing_slip_status=RoutingSlipStatus.REFUND_AUTHORIZED.value,
        refund_amount=100,
    )

    routing_slip = RoutingSlip.find_by_number(rs_1)
    factory_refund(
        routing_slip.id,
        {
            "name": "TEST",
            "mailingAddress": {
                "city": "Victoria",
                "region": "BC",
                "street": "655 Douglas St",
                "country": "CA",
                "postalCode": "V8V 0B6",
                "streetAdditional": "",
            },
        },
    )
    with patch("tasks.common.cgi_ejv.CgiEjv.upload") as mock_upload:
        ApTask.create_ap_files()
        mock_upload.assert_called()

    routing_slip = RoutingSlip.find_by_number(rs_1)
    assert routing_slip.status == RoutingSlipStatus.REFUND_UPLOADED.value

    # Run again and assert nothing is uploaded
    with patch("tasks.common.cgi_ejv.CgiEjv.upload") as mock_upload:
        ApTask.create_ap_files()
        mock_upload.assert_not_called()


def test_ap_disbursement(session, monkeypatch):
    """Test AP Disbursement for Non-government entities.

    Steps:
    1) Create invoices, payment line items with BCA corp type.
    2) Run the job and assert status
    """
    account = factory_create_pad_account(auth_account_id="1", status=CfsAccountStatus.ACTIVE.value)
    invoice = factory_invoice(
        payment_account=account,
        status_code=InvoiceStatus.PAID.value,
        total=10,
        corp_type_code="BCA",
    )
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type("BCA", "OLAARTOQ")
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    refund_invoice = factory_invoice(
        payment_account=account,
        status_code=InvoiceStatus.REFUNDED.value,
        total=10,
        disbursement_status_code=DisbursementStatus.COMPLETED.value,
        corp_type_code="BCA",
    )
    line = factory_payment_line_item(refund_invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    with patch("tasks.common.cgi_ejv.CgiEjv.upload") as mock_upload:
        ApTask.create_ap_files()
        mock_upload.assert_called()


def test_routing_slip_refund_error_handling(session, monkeypatch):
    """Test error handling in routing slip refund task."""
    mock_notification = MagicMock()
    monkeypatch.setattr("pay_api.services.email_service.JobFailureNotification.send_notification", mock_notification)
    rs_1 = "RS0000001"
    factory_routing_slip_account(
        number=rs_1,
        status=CfsAccountStatus.ACTIVE.value,
        total=100,
        remaining_amount=0,
        auth_account_id="1234",
        routing_slip_status=RoutingSlipStatus.REFUND_AUTHORIZED.value,
        refund_amount=100,
    )

    routing_slip = RoutingSlip.find_by_number(rs_1)
    factory_refund(
        routing_slip.id,
        {
            "name": "TEST",
            "mailingAddress": {
                "city": "Victoria",
                "region": "BC",
                "street": "655 Douglas St",
                "country": "CA",
                "postalCode": "V8V 0B6",
                "streetAdditional": "",
            },
        },
    )

    def mock_upload_error(*args, **kwargs):
        """Mock function to simulate upload error."""
        raise Exception("Failed to upload file")

    monkeypatch.setattr("tasks.common.cgi_ap.CgiAP.upload", mock_upload_error)

    ApTask.create_ap_files()
    mock_notification.assert_called_once()

    routing_slip = RoutingSlip.find_by_number(rs_1)
    assert routing_slip.status == RoutingSlipStatus.REFUND_AUTHORIZED.value


def test_get_ap_header_and_line_weekend_and_holiday_date_adjustment(session, monkeypatch):
    """Test that get_ap_header and get_ap_invoice_line use next business day.

    Tests scenario where Saturday and Sunday are weekends, and Monday is a
    holiday, so the next business day is Tuesday.

    Steps:
    1) Mock datetime.now() to return Saturday (June 29, 2024)
    2) Call get_ap_header and get_ap_invoice_line
    3) Assert that the effective_date is Tuesday (July 2, 2024),
       skipping Sunday and Monday holiday (Canada Day)
    """
    # June 29, 2024 is a Saturday, July 1, 2024 (Monday) is Canada Day holiday
    # July 2, 2024 (Tuesday) is the next business day
    saturday_date = datetime(2024, 6, 29, 12, 0, 0, tzinfo=UTC)
    expected_date = datetime(2024, 7, 2).date()

    with patch("tasks.common.cgi_ap.datetime") as mock_dt, patch("pay_api.utils.util.datetime") as mock_util_dt:

        def datetime_side_effect(*args, **kw):
            if args or kw:
                return datetime(*args, **kw)
            return datetime

        mock_dt.side_effect = datetime_side_effect
        mock_dt.now = lambda *_args, **_kwargs: saturday_date
        mock_dt.UTC = UTC

        mock_util_dt.side_effect = datetime_side_effect
        mock_util_dt.now = lambda *_args, **_kwargs: saturday_date
        mock_util_dt.UTC = UTC

        ap_header = APHeader(
            ap_flow=APFlow.NON_GOV_TO_EFT,
            total=100.00,
            invoice_number="TEST123",
            invoice_date=datetime.now(tz=UTC).date(),
            ap_supplier=APSupplier(),
        )

        ap_line = APLine(
            ap_flow=APFlow.NON_GOV_TO_EFT,
            total=100.00,
            invoice_number="TEST123",
            line_number=1,
            is_reversal=False,
            distribution="12345678901234567890",
            ap_supplier=APSupplier(),
        )

        header_result = CgiAP.get_ap_header(ap_header)
        line_result = CgiAP.get_ap_invoice_line(ap_line)

        header_date_match = re.search(r"CAD(\d{8})", header_result)
        assert header_date_match, "Could not find effective_date in header"
        header_effective_date_str = header_date_match.group(1)

        # Extract date from line: search for 8-digit date pattern (YYYYMMDD)
        # The date appears after the distribution code and padding
        # Look for date pattern starting with expected year (2024)
        expected_date_str = expected_date.strftime("%Y%m%d")
        line_date_match = re.search(re.escape(expected_date_str), line_result)
        assert line_date_match, (
            f"Could not find expected date {expected_date_str} in line. "
            f"Line preview: {line_result[:500]}"
        )
        line_effective_date_str = expected_date_str

        header_effective_date = datetime.strptime(header_effective_date_str, "%Y%m%d").date()
        line_effective_date = datetime.strptime(line_effective_date_str, "%Y%m%d").date()

        assert header_effective_date == expected_date, (
            f"Header effective_date {header_effective_date} "
            f"should be {expected_date} "
            f"(Tuesday, skipping weekend and holiday)"
        )
        assert line_effective_date == expected_date, (
            f"Line effective_date {line_effective_date} "
            f"should be {expected_date} "
            f"(Tuesday, skipping weekend and holiday)"
        )
