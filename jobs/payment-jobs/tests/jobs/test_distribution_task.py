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

"""Tests to assure the DistributionTask.

Test-Suite to ensure that the DistributionTask is working as expected.
"""
from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import FeeSchedule
from pay_api.utils.enums import InvoiceReferenceStatus, InvoiceStatus

from tasks.distribution_task import DistributionTask

from .factory import (
    factory_create_direct_pay_account,
    factory_create_ejv_account,
    factory_distribution,
    factory_distribution_link,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_line_item,
    factory_refund_invoice,
)
from .mocks import empty_refund_payload_response, paybc_token_response, refund_payload_response


def test_update_failed_distributions(session):
    """Test failed distribution payments ( 0 invoices )."""
    DistributionTask.update_failed_distributions()
    assert True


def test_update_failed_distributions_refunds(session, monkeypatch):
    """Test failed distribution refunds."""
    invoice = factory_invoice(
        factory_create_direct_pay_account(),
        status_code=InvoiceStatus.UPDATE_REVENUE_ACCOUNT_REFUND.value,
    )
    factory_invoice_reference(invoice.id, invoice.id, InvoiceReferenceStatus.COMPLETED.value)

    service_fee_distribution = factory_distribution(name="VS Service Fee", client="112")
    fee_distribution = factory_distribution(
        "Super Dist",
        service_fee_dist_id=service_fee_distribution.disbursement_distribution_code_id,
        client="112",
    )

    corp_type: CorpTypeModel = CorpTypeModel.find_by_code("VS")
    fee_schedule: FeeSchedule = FeeSchedule.find_by_filing_type_and_corp_type(corp_type.code, "WILLNOTICE")

    factory_distribution_link(fee_distribution.distribution_code_id, fee_schedule.fee_schedule_id)

    factory_payment_line_item(
        invoice.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        filing_fees=30,
        total=31.5,
        service_fees=1.5,
        fee_dist_id=fee_distribution.distribution_code_id,
    )

    factory_payment("PAYBC", "DIRECT_PAY", invoice_number=invoice.id)
    factory_refund_invoice(invoice.id)

    # Required, because mocking out the POST below (This uses the OAuthService POST).
    monkeypatch.setattr(
        "pay_api.services.direct_pay_service.DirectPayService.get_token",
        paybc_token_response,
    )
    # Mock POST until obtain OAS spec from PayBC for updating GL.
    monkeypatch.setattr("pay_api.services.oauth_service.OAuthService.post", lambda *args, **kwargs: None)
    # Mock refund payload response.
    monkeypatch.setattr("pay_api.services.oauth_service.OAuthService.get", refund_payload_response)

    DistributionTask.update_failed_distributions()
    assert invoice.invoice_status_code == InvoiceStatus.REFUNDED.value


def test_update_failed_distribution_payments(session, monkeypatch):
    """Test failed distribution payments."""
    invoice = factory_invoice(
        factory_create_direct_pay_account(),
        status_code=InvoiceStatus.UPDATE_REVENUE_ACCOUNT.value,
    )
    factory_invoice_reference(invoice.id, invoice.id, InvoiceReferenceStatus.COMPLETED.value)

    service_fee_distribution = factory_distribution(name="VS Service Fee", client="112")
    fee_distribution = factory_distribution(
        "Super Dist",
        service_fee_dist_id=service_fee_distribution.disbursement_distribution_code_id,
        client="112",
    )

    corp_type: CorpTypeModel = CorpTypeModel.find_by_code("VS")
    fee_schedule: FeeSchedule = FeeSchedule.find_by_filing_type_and_corp_type(corp_type.code, "WILLNOTICE")

    factory_distribution_link(fee_distribution.distribution_code_id, fee_schedule.fee_schedule_id)

    factory_payment_line_item(
        invoice.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        filing_fees=30,
        total=31.5,
        service_fees=1.5,
        fee_dist_id=fee_distribution.distribution_code_id,
    )

    factory_payment("PAYBC", "DIRECT_PAY", invoice_number=invoice.id)
    factory_refund_invoice(invoice.id)

    # Required, because we're mocking out the POST below (This uses the OAuthService POST).
    monkeypatch.setattr(
        "pay_api.services.direct_pay_service.DirectPayService.get_token",
        paybc_token_response,
    )
    # Mock POST until obtain OAS spec from PayBC for updating GL.
    monkeypatch.setattr("pay_api.services.oauth_service.OAuthService.post", lambda *args, **kwargs: None)

    DistributionTask.update_failed_distributions()
    assert invoice.invoice_status_code == InvoiceStatus.PAID.value


def test_non_direct_pay_invoices(session, monkeypatch):
    """Test non DIRECT_PAY invoices."""
    invoice = factory_invoice(
        factory_create_ejv_account(),
        status_code=InvoiceStatus.UPDATE_REVENUE_ACCOUNT.value,
    )
    factory_invoice_reference(invoice.id, invoice.id, InvoiceReferenceStatus.COMPLETED.value)
    factory_payment("PAYBC", "EJV", invoice_number=invoice.id)
    DistributionTask.update_failed_distributions()
    assert invoice.invoice_status_code == InvoiceStatus.PAID.value

    invoice = factory_invoice(
        factory_create_ejv_account(),
        status_code=InvoiceStatus.UPDATE_REVENUE_ACCOUNT_REFUND.value,
    )
    factory_invoice_reference(invoice.id, invoice.id, InvoiceReferenceStatus.COMPLETED.value)
    factory_payment("PAYBC", "EJV", invoice_number=invoice.id)
    factory_refund_invoice(invoice.id)
    DistributionTask.update_failed_distributions()
    assert invoice.invoice_status_code == InvoiceStatus.REFUNDED.value


def test_no_response_pay_bc(session, monkeypatch):
    """Test no response from PayBC."""
    invoice = factory_invoice(factory_create_direct_pay_account(), status_code=InvoiceStatus.PAID.value)
    monkeypatch.setattr("pay_api.services.oauth_service.OAuthService.get", empty_refund_payload_response)
    assert invoice.invoice_status_code == InvoiceStatus.PAID.value
