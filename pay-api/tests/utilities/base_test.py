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

"""A helper test.

Test-Suite to ensure that the /payments endpoint is working as expected.
"""

from datetime import datetime

from pay_api.models import Invoice, InvoiceReference, Payment, PaymentAccount, PaymentLineItem, PaymentTransaction
from pay_api.utils.enums import Role, Status


token_header = {
    'alg': 'RS256',
    'typ': 'JWT',
    'kid': 'sbc-auth-cron-job'
}


def get_claims(app_request=None, role: str = Role.EDITOR.value, username: str = 'CP0001234', login_source: str = None):
    """Return the claim with the role param."""
    claim = {
        'jti': 'a50fafa4-c4d6-4a9b-9e51-1e5e0d102878',
        'exp': 31531718745,
        'iat': 1531718745,
        'iss': app_request.config[
            'JWT_OIDC_ISSUER'] if app_request else 'https://sso-dev.pathfinder.gov.bc.ca/auth/realms/fcf0kpqr',
        'aud': 'sbc-auth-web',
        'sub': '15099883-3c3f-4b4c-a124-a1824d6cba84',
        'typ': 'Bearer',
        'realm_access':
            {
                'roles':
                    [
                        '{}'.format(role)
                    ]
            },
        'preferred_username': username,
        'username': username,
        'loginSource': login_source
    }
    return claim


def get_payment_request(business_identifier: str = 'CP0001234'):
    """Return a payment request object."""
    return {
        'paymentInfo': {
            'methodOfPayment': 'CC'
        },
        'businessInfo': {
            'businessIdentifier': business_identifier,
            'corpType': 'CP',
            'businessName': 'ABC Corp',
            'contactInfo': {
                'city': 'Victoria',
                'postalCode': 'V8P2P2',
                'province': 'BC',
                'addressLine1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filingInfo': {
            'filingTypes': [
                {
                    'filingTypeCode': 'OTADD',
                    'filingDescription': 'TEST'
                },
                {
                    'filingTypeCode': 'OTANN'
                }
            ]
        }
    }


def get_zero_dollar_payment_request(business_identifier: str = 'CP0001234'):
    """Return a payment request object."""
    return {
        'paymentInfo': {
            'methodOfPayment': 'CC'
        },
        'businessInfo': {
            'businessIdentifier': business_identifier,
            'corpType': 'CP',
            'businessName': 'ABC Corp',
            'contactInfo': {
                'city': 'Victoria',
                'postalCode': 'V8P2P2',
                'province': 'BC',
                'addressLine1': '100 Douglas Street',
                'country': 'CA'
            }
        },
        'filingInfo': {
            'filingTypes': [
                {
                    'filingTypeCode': 'OTFDR'
                },
                {
                    'filingTypeCode': 'OTFDR'
                }
            ]
        }
    }


def factory_payment_account(corp_number: str = 'CP0001234', corp_type_code: str = 'CP',
                            payment_system_code: str = 'PAYBC'):
    """Factory."""
    return PaymentAccount(
        corp_number=corp_number,
        corp_type_code=corp_type_code,
        payment_system_code=payment_system_code,
        party_number='11111',
        account_number='4101',
        site_number='29921',
    )


def factory_payment(
        payment_system_code: str = 'PAYBC', payment_method_code: str = 'CC',
        payment_status_code: str = Status.DRAFT.value
):
    """Factory."""
    return Payment(
        payment_system_code=payment_system_code,
        payment_method_code=payment_method_code,
        payment_status_code=payment_status_code,
        created_by='test',
        created_on=datetime.now(),
    )


def factory_invoice(payment_id: str, account_id: str, status_code: str = Status.DRAFT.value):
    """Factory."""
    return Invoice(
        payment_id=payment_id,
        invoice_status_code=status_code,
        account_id=account_id,
        total=0,
        created_by='test',
        created_on=datetime.now(),
    )


def factory_payment_line_item(invoice_id: str, fee_schedule_id: int, filing_fees: int = 10, total: int = 10, status:str=Status.CREATED.value):
    """Factory."""
    return PaymentLineItem(
        invoice_id=invoice_id,
        fee_schedule_id=fee_schedule_id,
        filing_fees=filing_fees,
        total=total,
        line_item_status_code=status,
    )


def factory_payment_transaction(
        payment_id: str,
        status_code: str = 'DRAFT',
        client_system_url: str = 'http://google.com/',
        pay_system_url: str = 'http://google.com',
        transaction_start_time: datetime = datetime.now(),
        transaction_end_time: datetime = datetime.now(),
):
    """Factory."""
    return PaymentTransaction(
        payment_id=payment_id,
        status_code=status_code,
        client_system_url=client_system_url,
        pay_system_url=pay_system_url,
        transaction_start_time=transaction_start_time,
        transaction_end_time=transaction_end_time,
    )


def factory_invoice_reference(invoice_id: int, invoice_number: str = '10021'):
    """Factory."""
    return InvoiceReference(invoice_id=invoice_id,
                            status_code='CREATED',
                            invoice_number=invoice_number)
