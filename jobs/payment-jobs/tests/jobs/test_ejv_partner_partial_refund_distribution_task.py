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

"""Tests to assure the CGI EJV Job.

Test-Suite to ensure that the CgiEjvJob is working as expected.
"""
from datetime import datetime, timedelta, timezone

import pytest
from flask import current_app
from freezegun import freeze_time
from pay_api.models import CorpType as CorpTypeModel
from pay_api.models import DistributionCode, EjvFile, EjvHeader, EjvLink, FeeSchedule
from pay_api.models import PartnerDisbursements as PartnerDisbursementsModel
from pay_api.models import db
from pay_api.utils.enums import CfsAccountStatus, DisbursementStatus, EJVLinkType, PaymentMethod, RefundsPartialType

from tasks.ejv_partner_distribution_task import EjvPartnerDistributionTask

from .factory import (
    factory_create_direct_pay_account,
    factory_create_online_banking_account,
    factory_create_pad_account,
    factory_distribution,
    factory_distribution_link,
    factory_invoice,
    factory_invoice_reference,
    factory_payment,
    factory_payment_line_item,
    factory_refund_partial,
)


@pytest.mark.parametrize(
    "account_factory,payment_method,cfs_account_status",
    [
        (factory_create_pad_account, PaymentMethod.PAD.value, True),
        (factory_create_online_banking_account, PaymentMethod.ONLINE_BANKING.value, True),
        (factory_create_direct_pay_account, PaymentMethod.DIRECT_PAY.value, False),
    ],
)
def test_partial_refund_disbursement_with_payment_method(
    session, monkeypatch, account_factory, payment_method, cfs_account_status
):
    """Test partial refund disbursement for different payment methods."""
    monkeypatch.setattr("pysftp.Connection.put", lambda *args, **kwargs: None)
    corp_type: CorpTypeModel = CorpTypeModel.find_by_code("VS")

    if cfs_account_status:
        pay_account = account_factory(status=CfsAccountStatus.ACTIVE.value)
    else:
        pay_account = account_factory()

    disbursement_distribution: DistributionCode = factory_distribution(name="VS Disbursement", client="112")
    service_fee_distribution: DistributionCode = factory_distribution(name="VS Service Fee", client="112")
    fee_distribution: DistributionCode = factory_distribution(
        name="VS Fee distribution",
        client="112",
        service_fee_dist_id=service_fee_distribution.distribution_code_id,
        disbursement_dist_id=disbursement_distribution.distribution_code_id,
    )
    fee_schedule: FeeSchedule = FeeSchedule.find_by_filing_type_and_corp_type(corp_type.code, "WILLNOTICE")
    factory_distribution_link(fee_distribution.distribution_code_id, fee_schedule.fee_schedule_id)

    invoice = factory_invoice(
        payment_account=pay_account,
        disbursement_status_code=DisbursementStatus.COMPLETED.value,
        corp_type_code=corp_type.code,
        total=21.5,
        status_code="PAID",
    )
    pli = factory_payment_line_item(
        invoice_id=invoice.id,
        fee_schedule_id=fee_schedule.fee_schedule_id,
        filing_fees=0,
        total=1.5,
        service_fees=1.5,
        fee_dist_id=fee_distribution.distribution_code_id,
    )

    inv_ref = factory_invoice_reference(invoice_id=invoice.id)
    factory_payment(invoice_number=inv_ref.invoice_number, payment_status_code="COMPLETED")

    refund_partial = factory_refund_partial(
        pli.id,
        invoice_id=invoice.id,
        refund_amount=1.5,
        created_by="test",
        refund_type=RefundsPartialType.SERVICE_FEES.value,
    )

    partner_disbursement = PartnerDisbursementsModel(
        amount=refund_partial.refund_amount,
        is_reversal=True,
        target_id=refund_partial.id,
        target_type=EJVLinkType.PARTIAL_REFUND.value,
        partner_code=corp_type.code,
        status_code=DisbursementStatus.WAITING_FOR_JOB.value
    ).save()

    assert refund_partial.disbursement_status_code is None
    assert partner_disbursement.status_code == DisbursementStatus.WAITING_FOR_JOB.value

    refund_partial_link = EjvLink.find_ejv_link_by_link_id(refund_partial.id)
    assert refund_partial_link is None

    day_after_time_delay = datetime.now(tz=timezone.utc) + timedelta(
        days=(current_app.config.get("DISBURSEMENT_DELAY_IN_DAYS") + 1)
    )

    with freeze_time(day_after_time_delay):
        EjvPartnerDistributionTask.create_ejv_file()

        ejv_link = db.session.query(EjvLink).filter(EjvLink.link_id == refund_partial.id).first()
        assert ejv_link

        ejv_header = db.session.query(EjvHeader).filter(EjvHeader.id == ejv_link.ejv_header_id).first()
        assert ejv_header
        assert ejv_header.disbursement_status_code == DisbursementStatus.UPLOADED.value

        ejv_file = EjvFile.find_by_id(ejv_header.ejv_file_id)
        assert ejv_file
        assert ejv_file.disbursement_status_code == DisbursementStatus.UPLOADED.value

    refund_partial_link = EjvLink.find_ejv_link_by_link_id(refund_partial.id)
    assert refund_partial_link.disbursement_status_code == DisbursementStatus.UPLOADED.value
    assert refund_partial.disbursement_status_code == DisbursementStatus.UPLOADED.value

    updated_partner_disbursement = PartnerDisbursementsModel.find_by_id(partner_disbursement.id)
    assert updated_partner_disbursement.status_code == DisbursementStatus.UPLOADED.value
