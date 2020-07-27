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

from pay_api.models import (
    BcolPaymentAccount, CreditPaymentAccount, InternalPaymentAccount, Invoice, InvoiceReference, Payment,
    PaymentAccount, PaymentLineItem, PaymentTransaction, DistributionCode)
from pay_api.utils.enums import PaymentSystem, Role, PaymentStatus, InvoiceReferenceStatus, \
    LineItemStatus, InvoiceStatus

token_header = {
    'alg': 'RS256',
    'typ': 'JWT',
    'kid': 'sbc-auth-web'
}


def get_claims(app_request=None, role: str = Role.EDITOR.value, username: str = 'CP0001234', login_source: str = None,
               roles: list = []):
    """Return the claim with the role param."""
    claim = {
        'jti': 'a50fafa4-c4d6-4a9b-9e51-1e5e0d102878',
        'exp': 31531718745,
        'iat': 1531718745,
        'iss': 'http://localhost:8081/auth/realms/demo',
        'aud': 'sbc-auth-web',
        'sub': '15099883-3c3f-4b4c-a124-a1824d6cba84',
        'typ': 'Bearer',
        'realm_access':
            {
                'roles':
                    [
                        '{}'.format(role),
                        *roles
                    ]
            },
        'preferred_username': username,
        'username': username,
        'loginSource': login_source
    }
    return claim


def get_payment_request(business_identifier: str = 'CP0001234', corp_type: str = 'CP',
                        second_filing_type: str = 'OTADD'):
    """Return a payment request object."""
    return {
        'businessInfo': {
            'businessIdentifier': business_identifier,
            'corpType': corp_type,
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
                    'filingTypeCode': second_filing_type,
                    'filingDescription': 'TEST'
                },
                {
                    'filingTypeCode': 'OTANN'
                }
            ]
        }
    }


def get_payment_request_with_service_fees(business_identifier: str = 'CP0001234', corp_type: str = 'BC',
                                          filing_type: str = 'BCINC'):
    """Return a payment request object."""
    return {
        'businessInfo': {
            'businessIdentifier': business_identifier,
            'corpType': corp_type,
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
                    'filingTypeCode': filing_type
                }
            ]
        }
    }


def get_payment_request_with_folio_number(business_identifier: str = 'CP0001234', folio_number: str = '1234567890'):
    """Return a payment request object."""
    return {
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
            'folioNumber': folio_number,
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


def get_payment_request_with_payment_method(business_identifier: str = 'CP0001234', payment_method: str = 'CC'):
    """Return a payment request object."""
    return {
        'paymentInfo': {
            'methodOfPayment': payment_method
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


def get_payment_request_with_no_contact_info(payment_method: str = 'CC', corp_type: str = 'CP'):
    """Return a payment request object."""
    return {
        'paymentInfo': {
            'methodOfPayment': payment_method
        },
        'businessInfo': {
            'corpType': corp_type
        },
        'filingInfo': {
            'filingTypes': [
                {
                    'filingTypeCode': 'SERCH'
                }
            ]
        }
    }


def get_zero_dollar_payment_request(business_identifier: str = 'CP0001234'):
    """Return a payment request object."""
    return {
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


def get_waive_fees_payment_request(business_identifier: str = 'CP0001234'):
    """Return a payment request object."""
    return {
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
                    'filingTypeCode': 'OTANN',
                    'waiveFees': True
                },
                {
                    'filingTypeCode': 'OTCDR',
                    'waiveFees': True
                }
            ]
        }
    }


def factory_payment_account(corp_number: str = 'CP0001234', corp_type_code: str = 'CP',
                            payment_system_code: str = 'PAYBC', account_number='4101', bcol_user_id='test',
                            auth_account_id: str = '1234'):
    """Return Factory."""
    # Create a payment account
    account = PaymentAccount(auth_account_id=auth_account_id).save()

    if payment_system_code == PaymentSystem.BCOL.value:
        return BcolPaymentAccount(
            bcol_user_id=bcol_user_id,
            bcol_account_id='TEST',
            account_id=account.id,

        )
    elif payment_system_code == PaymentSystem.PAYBC.value:
        return CreditPaymentAccount(
            corp_number=corp_number,
            corp_type_code=corp_type_code,
            paybc_party='11111',
            paybc_account=account_number,
            paybc_site='29921',
            account_id=account.id
        )
    elif payment_system_code == PaymentSystem.INTERNAL.value:
        return InternalPaymentAccount(
            corp_number=corp_number,
            corp_type_code=corp_type_code,
            account_id=account.id
        )


def factory_premium_payment_account(corp_number: str = 'CP0001234', corp_type_code: str = 'CP',
                                    payment_system_code: str = 'BCOL',
                                    bcol_user_id='PB25020', bcol_account_id='1234567890', auth_account_id='1234'):
    """Return Factory."""
    account = PaymentAccount(auth_account_id=auth_account_id).save()

    return BcolPaymentAccount(
        bcol_user_id=bcol_user_id,
        bcol_account_id=bcol_account_id,
        account_id=account.id
    )


def factory_payment(
        payment_system_code: str = 'PAYBC', payment_method_code: str = 'CC',
        payment_status_code: str = PaymentStatus.CREATED.value,
        created_on: datetime = datetime.now()
):
    """Return Factory."""
    return Payment(
        payment_system_code=payment_system_code,
        payment_method_code=payment_method_code,
        payment_status_code=payment_status_code,
        created_by='test',
        created_on=created_on,
    )


def factory_invoice(payment: Payment, payment_account: str, status_code: str = InvoiceStatus.CREATED.value,
                    corp_type_code='CP',
                    business_identifier: str = 'CP0001234',
                    service_fees: float = 0.0):
    """Return Factory."""
    bcol_account_id = None
    credit_account_id = None
    internal_account_id = None
    if isinstance(payment_account, BcolPaymentAccount):
        bcol_account_id = payment_account.id
    elif isinstance(payment_account, InternalPaymentAccount):
        internal_account_id = payment_account.id
    if isinstance(payment_account, CreditPaymentAccount):
        credit_account_id = payment_account.id

    return Invoice(
        payment_id=payment.id,
        invoice_status_code=status_code,
        bcol_account_id=bcol_account_id,
        credit_account_id=credit_account_id,
        internal_account_id=internal_account_id,
        total=0,
        created_by='test',
        created_on=datetime.now(),
        business_identifier=business_identifier,
        corp_type_code=corp_type_code,
        folio_number='1234567890',
        service_fees=service_fees
    )


def factory_payment_line_item(invoice_id: str, fee_schedule_id: int, filing_fees: int = 10, total: int = 10,
                              status: str = LineItemStatus.ACTIVE.value):
    """Return Factory."""
    return PaymentLineItem(
        invoice_id=invoice_id,
        fee_schedule_id=fee_schedule_id,
        filing_fees=filing_fees,
        total=total,
        line_item_status_code=status,
        fee_distribution_id=DistributionCode.find_by_active_for_fee_schedule(fee_schedule_id).distribution_code_id
    )


def factory_payment_transaction(
        payment_id: str,
        status_code: str = 'CREATED',
        client_system_url: str = 'http://google.com/',
        pay_system_url: str = 'http://google.com',
        transaction_start_time: datetime = datetime.now(),
        transaction_end_time: datetime = datetime.now(),
):
    """Return Factory."""
    return PaymentTransaction(
        payment_id=payment_id,
        status_code=status_code,
        client_system_url=client_system_url,
        pay_system_url=pay_system_url,
        transaction_start_time=transaction_start_time,
        transaction_end_time=transaction_end_time,
    )


def factory_invoice_reference(invoice_id: int, invoice_number: str = '10021'):
    """Return Factory."""
    return InvoiceReference(invoice_id=invoice_id,
                            status_code=InvoiceReferenceStatus.ACTIVE.value,
                            invoice_number=invoice_number)


def get_paybc_transaction_request():
    """Return a stub payment transaction request."""
    return {
        'clientSystemUrl': 'http://localhost:8080/abcd',
        'payReturnUrl': 'http://localhost:8081/xyz'
    }


def get_auth_basic_user():
    """Return authorization response for basic users."""
    return {
        'orgMembership': 'OWNER',
        'roles': [
            'view',
            'edit'
        ],
        'business': {
            'folioNumber': 'MOCK1234',
            'name': 'Mock Business'
        },
        'account': {
            'accountType': 'BASIC',
            'id': '1234',
            'name': 'Mock Account',
            'paymentPreference': {
                'methodOfPayment': 'CC',
                'bcOnlineUserId': '',
                'bcOnlineAccountId': ''
            }
        }
    }


def get_auth_premium_user():
    """Return authorization response for basic users."""
    return {
        'orgMembership': 'OWNER',
        'roles': [
            'view',
            'edit'
        ],
        'business': {
            'folioNumber': 'MOCK1234',
            'name': 'Mock Business'
        },
        'account': {
            'accountType': 'PREMIUM',
            'id': '1234',
            'name': 'Mock Account',
            'paymentPreference': {
                'methodOfPayment': 'DRAWDOWN',
                'bcOnlineUserId': 'PB25020',
                'bcOnlineAccountId': '1234567890'
            }
        }
    }


def get_distribution_code_payload(client: str = '100'):
    """Return distribution code payload."""
    return {
        'client': client,
        'memoName': 'Test Memo Line',
        'projectCode': '1111111',
        'responsibilityCentre': '22222',
        'serviceFeeClient': '101',
        'serviceFeeLine': '1111111',
        'serviceFeeMemoName': 'Test Memo Line Service Fee',
        'serviceFeeProjectCode': '1111111',
        'serviceFeeResponsibilityCentre': '22222',
        'serviceFeeStob': '9001',
        'serviceLine': '1111111',
        'stob': '9000'
    }


def get_distribution_schedules_payload():
    """Return distribution schedule payload."""
    return [{
        'feeScheduleId': 1
    }]
