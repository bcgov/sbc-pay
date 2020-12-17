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

"""Tests to assure the Direct Payment Service."""

import urllib.parse

from flask import current_app

from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import FeeSchedule
from pay_api.services.direct_pay_service import DirectPayService, PAYBC_DATE_FORMAT, DECIMAL_PRECISION
from pay_api.services.distribution_code import DistributionCode
from pay_api.services.hashing import HashingService
from pay_api.utils.util import generate_transaction_number, current_local_time
from tests.utilities.base_test import (
    factory_invoice, factory_invoice_reference, factory_payment, factory_payment_account, factory_payment_line_item)
from tests.utilities.base_test import get_distribution_code_payload


def test_get_payment_system_url(session, public_user_mock):
    """Assert that the url returned is correct."""
    today = current_local_time().strftime(PAYBC_DATE_FORMAT)
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_ref = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    distribution_code = DistributionCodeModel.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    distribution_code_svc = DistributionCode()
    distribution_code_payload = get_distribution_code_payload()
    # update the existing gl code with new values
    distribution_code_svc.save_or_update(distribution_code_payload,
                                         distribution_code.distribution_code_id)
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id)
    line.save()
    direct_pay_service = DirectPayService()
    payment_response_url = direct_pay_service.get_payment_system_url_for_invoice(invoice, invoice_ref, 'google.com')
    url_param_dict = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(payment_response_url).query))
    assert url_param_dict['trnDate'] == today
    assert url_param_dict['glDate'] == today
    assert url_param_dict['description'] == 'Direct_Sale'
    assert url_param_dict['pbcRefNumber'] == current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER')
    assert url_param_dict['trnNumber'] == generate_transaction_number(invoice.id)
    assert url_param_dict['trnAmount'] == str(invoice.total)
    assert url_param_dict['paymentMethod'] == 'CC'
    assert url_param_dict['redirectUri'] == 'google.com'
    revenue_str = f"1:{distribution_code_payload['client']}." \
        f"{distribution_code_payload['responsibilityCentre']}." \
        f"{distribution_code_payload['serviceLine']}." \
        f"{distribution_code_payload['stob']}." \
        f"{distribution_code_payload['projectCode']}." \
        f'000000.0000:10.00'
    assert url_param_dict['revenue'] == revenue_str
    urlstring = f"trnDate={today}&pbcRefNumber={current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER')}&" \
        f'glDate={today}&description=Direct_Sale&' \
        f'trnNumber={generate_transaction_number(invoice.id)}&' \
        f'trnAmount={invoice.total}&' \
        f'paymentMethod=CC&' \
        f'redirectUri=google.com&' \
        f'currency=CAD&' \
        f'revenue={revenue_str}'
    expected_hash_str = HashingService.encode(urlstring)
    assert expected_hash_str == url_param_dict['hashValue']


def test_get_payment_system_url_service_fees(session, public_user_mock):
    """Assert that the url returned is correct."""
    today = current_local_time().strftime(PAYBC_DATE_FORMAT)
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_ref = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    distribution_code = DistributionCodeModel.find_by_active_for_fee_schedule(fee_schedule.fee_schedule_id)
    distribution_code_svc = DistributionCode()
    distribution_code_payload = get_distribution_code_payload()
    # update the existing gl code with new values
    distribution_code_svc.save_or_update(distribution_code_payload,
                                         distribution_code.distribution_code_id)
    service_fee = 100
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id, service_fees=service_fee)
    line.save()
    direct_pay_service = DirectPayService()
    payment_response_url = direct_pay_service.get_payment_system_url_for_invoice(invoice, invoice_ref, 'google.com')
    url_param_dict = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(payment_response_url).query))
    assert url_param_dict['trnDate'] == today
    assert url_param_dict['glDate'] == today
    assert url_param_dict['description'] == 'Direct_Sale'
    assert url_param_dict['pbcRefNumber'] == current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER')
    assert url_param_dict['trnNumber'] == generate_transaction_number(invoice.id)
    assert url_param_dict['trnAmount'] == str(invoice.total)
    assert url_param_dict['paymentMethod'] == 'CC'
    assert url_param_dict['redirectUri'] == 'google.com'
    revenue_str = f"1:{distribution_code_payload['client']}." \
        f"{distribution_code_payload['responsibilityCentre']}." \
        f"{distribution_code_payload['serviceLine']}." \
        f"{distribution_code_payload['stob']}." \
        f"{distribution_code_payload['projectCode']}." \
        f'000000.0000:10.00'
    revenue_str_service_fee = f"2:{distribution_code_payload['serviceFeeClient']}." \
        f"{distribution_code_payload['serviceFeeResponsibilityCentre']}." \
        f"{distribution_code_payload['serviceFeeLine']}." \
        f"{distribution_code_payload['serviceFeeStob']}." \
        f"{distribution_code_payload['serviceFeeProjectCode']}." \
        f'000000.0000:{format(service_fee, DECIMAL_PRECISION)}'
    assert url_param_dict['revenue'] == f'{revenue_str}|{revenue_str_service_fee}'
    urlstring = f"trnDate={today}&pbcRefNumber={current_app.config.get('PAYBC_DIRECT_PAY_REF_NUMBER')}&" \
        f'glDate={today}&description=Direct_Sale&' \
        f'trnNumber={generate_transaction_number(invoice.id)}&' \
        f'trnAmount={invoice.total}&' \
        f'paymentMethod=CC&' \
        f'redirectUri=google.com&' \
        f'currency=CAD&' \
        f'revenue={revenue_str}|' \
        f'{revenue_str_service_fee}'
    expected_hash_str = HashingService.encode(urlstring)

    assert expected_hash_str == url_param_dict['hashValue']


def test_get_receipt(session, public_user_mock):
    """Assert that get receipt is working."""
    response_url = 'trnApproved=1&messageText=Approved&trnOrderId=1003598&trnAmount=201.00&paymentMethod=CC' \
                   '&cardType=VI&authCode=TEST&trnDate=2020-08-11&pbcTxnNumber=1'
    invalid_hash = '&hashValue=0f7953db6f02f222f1285e1544c6a765'
    payment_account = factory_payment_account()
    payment = factory_payment()
    payment_account.save()
    payment.save()
    invoice = factory_invoice(payment_account)
    invoice.save()
    invoice_ref = factory_invoice_reference(invoice.id).save()
    fee_schedule = FeeSchedule.find_by_filing_type_and_corp_type('CP', 'OTANN')
    service_fee = 100
    line = factory_payment_line_item(invoice.id, fee_schedule_id=fee_schedule.fee_schedule_id, service_fees=service_fee)
    line.save()
    direct_pay_service = DirectPayService()
    rcpt = direct_pay_service.get_receipt(payment_account, f'{response_url}{invalid_hash}', invoice_ref)
    assert rcpt is None

    valid_hash = f'&hashValue={HashingService.encode(response_url)}'
    rcpt = direct_pay_service.get_receipt(payment_account, f'{response_url}{valid_hash}', invoice_ref)
    assert rcpt is not None

    # Test receipt without response_url
    rcpt = direct_pay_service.get_receipt(payment_account, None, invoice_ref)
    assert rcpt is not None
