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
from unittest.mock import patch

from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import RoutingSlip
from pay_api.utils.enums import CfsAccountStatus, DisbursementStatus, InvoiceStatus, RoutingSlipStatus

from tasks.ap_task import ApTask

from .factory import (
    factory_create_pad_account, factory_invoice, factory_payment_line_item, factory_refund,
    factory_routing_slip_account)


def test_routing_slip_refunds(session, monkeypatch):
    """Test Routing slip AP refund job.

    Steps:
    1) Create a routing slip with remaining_amount and status REFUND_AUTHORIZED
    2) Run the job and assert status
    """
    rs_1 = 'RS0000001'
    factory_routing_slip_account(
        number=rs_1,
        status=CfsAccountStatus.ACTIVE.value,
        total=100,
        remaining_amount=0,
        auth_account_id='1234',
        routing_slip_status=RoutingSlipStatus.REFUND_AUTHORIZED.value,
        refund_amount=100)

    routing_slip = RoutingSlip.find_by_number(rs_1)
    factory_refund(routing_slip.id, {
        'name': 'TEST',
        'mailingAddress': {
            'city': 'Victoria',
            'region': 'BC',
            'street': '655 Douglas St',
            'country': 'CA',
            'postalCode': 'V8V 0B6',
            'streetAdditional': ''
        }
    })
    with patch('pysftp.Connection.put') as mock_upload:
        ApTask.create_ap_files()
        mock_upload.assert_called()

    routing_slip = RoutingSlip.find_by_number(rs_1)
    assert routing_slip.status == RoutingSlipStatus.REFUND_UPLOADED.value

    # Run again and assert nothing is uploaded
    with patch('pysftp.Connection.put') as mock_upload:
        ApTask.create_ap_files()
        mock_upload.assert_not_called()


def test_ap_disbursement(session, monkeypatch):
    """Test AP Disbursement for Non-government entities.

    Steps:
    1) Create invoices, payment line items with BCA corp type.
    2) Run the job and assert status
    """
    account = factory_create_pad_account(auth_account_id='1', status=CfsAccountStatus.ACTIVE.value)
    invoice = factory_invoice(
        payment_account=account,
        status_code=InvoiceStatus.PAID.value,
        total=10,
        corp_type_code='BCA'
    )
    fee_schedule = FeeScheduleModel.find_by_filing_type_and_corp_type('BCA', 'OLAARTOQ')
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()

    refund_invoice = factory_invoice(
        payment_account=account,
        status_code=InvoiceStatus.REFUNDED.value,
        total=10,
        disbursement_status_code=DisbursementStatus.COMPLETED.value,
        corp_type_code='BCA'
    )
    line = factory_payment_line_item(refund_invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    with patch('pysftp.Connection.put') as mock_upload:
        ApTask.create_ap_files()
        mock_upload.assert_called()
