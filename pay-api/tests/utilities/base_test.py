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

"""A helper test.

Test-Suite to ensure that the /payments endpoint is working as expected.
"""

from datetime import datetime, timezone
from decimal import Decimal
from random import randrange
from typing import Dict, List, Tuple

from faker import Faker

from pay_api.models import (
    CfsAccount, Comment, DistributionCode, DistributionCodeLink, EFTFile, EFTShortnameLinks, EFTShortnames, Invoice,
    InvoiceReference, NonSufficientFundsModel, Payment, PaymentAccount, PaymentLineItem, PaymentTransaction, Receipt,
    RoutingSlip, Statement, StatementInvoices, StatementSettings)
from pay_api.utils.constants import DT_SHORT_FORMAT
from pay_api.utils.enums import (
    CfsAccountStatus, EFTShortnameStatus, InvoiceReferenceStatus, InvoiceStatus, LineItemStatus, PaymentMethod,
    PaymentStatus, PaymentSystem, Role, RoutingSlipStatus)


token_header = {
    'alg': 'RS256',
    'typ': 'JWT',
    'kid': 'sbc-auth-web'
}

fake = Faker()


def get_claims(app_request=None, role: str = Role.EDITOR.value, username: str = 'CP0001234', login_source: str = None,
               roles: list = [], product_code: str = 'BUSINESS'):
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
        'name': username,
        'username': username,
        'loginSource': login_source,
        'roles':
            [
                '{}'.format(role),
                *roles
            ],
        'product_code': product_code
    }
    return claim


def get_routing_slip_payment_request(business_identifier: str = 'CP0001234', corp_type: str = 'CP',
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
        'accountInfo': {
            'routingSlip': '123456789'
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


def get_payment_request_without_bn(corp_type: str = 'CP',
                                   filing_type: str = 'OTADD'):
    """Return a payment request object."""
    return {
        'businessInfo': {
            'corpType': corp_type
        },
        'filingInfo': {
            'filingTypes': [
                {
                    'filingTypeCode': filing_type,
                    'filingDescription': 'TEST'
                },
                {
                    'filingTypeCode': 'OTANN'
                }
            ]
        }
    }


def get_payment_request_with_service_fees(business_identifier: str = 'CP0001234', corp_type: str = 'BEN',
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


def get_payment_request_for_cso(csbfile_quantity: int = 2):
    """Return a payment request object for cso."""
    return {
        'filingInfo': {
            'filingIdentifier': '34522',
            'folioNumber': '22',
            'filingTypes': [{
                'filingTypeCode': 'CSBVFEE',
                'quantity': csbfile_quantity
            }]
        },
        'businessInfo': {
            'businessIdentifier': 'business_indentifier',
            'businessName': 'business_name',
            'corpType': 'CSO'
        },
        'details': [{
            'label': 'A Label',
            'value': 'A value'
        }]
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
            'filingIdentifier': '34522',
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


def get_payment_request_with_no_contact_info(payment_method: str = 'CC', corp_type: str = 'CP',
                                             filing_type_code: str = 'SERCH', future_effective: bool = False):
    """Return a payment request object."""
    return {
        'paymentInfo': {
            'methodOfPayment': payment_method
        },
        'businessInfo': {
            'corpType': corp_type,
            'businessIdentifier': 'CP8765768'
        },
        'filingInfo': {
            'filingTypes': [
                {
                    'filingTypeCode': filing_type_code,
                    'futureEffective': future_effective
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


def get_payment_request_for_wills(will_alias_quantity: int = 1):
    """Return a payment request object for wills."""
    return {
        'businessInfo': {
            'corpType': 'VS'
        },
        'filingInfo': {
            'filingTypes': [
                {
                    'filingTypeCode': 'WILLNOTICE'
                },
                {
                    'filingTypeCode': 'WILLALIAS',
                    'quantity': will_alias_quantity
                }
            ]
        }
    }


def factory_payment_account(payment_system_code: str = 'PAYBC', payment_method_code: str = 'CC', account_number='4101',
                            bcol_user_id='test',
                            auth_account_id: str = '1234',
                            cfs_account_status: str = CfsAccountStatus.ACTIVE.value,
                            name=None,
                            branch_name=None):
    """Return Factory."""
    # Create a payment account
    account = PaymentAccount(
        auth_account_id=auth_account_id,
        bcol_user_id=bcol_user_id,
        bcol_account='TEST',
        name=name,
        branch_name=branch_name,
        payment_method=payment_method_code,
        pad_activation_date=datetime.now(tz=timezone.utc),
        eft_enable=False
    ).save()

    CfsAccount(cfs_party='11111',
               cfs_account=account_number,
               cfs_site='29921',
               account_id=account.id,
               status=cfs_account_status).save()

    if payment_system_code == PaymentSystem.BCOL.value:
        account.payment_method = PaymentMethod.DRAWDOWN.value
    elif payment_system_code == PaymentSystem.PAYBC.value:
        account.payment_method = payment_method_code

    return account


def factory_premium_payment_account(bcol_user_id='PB25020', bcol_account_id='1234567890', auth_account_id='1234'):
    """Return Factory."""
    account = PaymentAccount(auth_account_id=auth_account_id,
                             bcol_user_id=bcol_user_id,
                             bcol_account=bcol_account_id,
                             eft_enable=False
                             )
    return account


def factory_payment(
        payment_system_code: str = 'PAYBC', payment_method_code: str = 'CC',
        payment_status_code: str = PaymentStatus.CREATED.value,
        invoice_number: str = None,
        payment_account_id: str = None,
        invoice_amount=0,
        paid_amount=0
):
    """Return Factory."""
    payment: Payment = Payment(
        payment_system_code=payment_system_code,
        payment_method_code=payment_method_code,
        payment_status_code=payment_status_code,
        invoice_number=invoice_number,
        payment_account_id=payment_account_id,
        invoice_amount=invoice_amount,
        paid_amount=paid_amount
    )
    return payment


def factory_usd_payment(
        payment_system_code: str = 'PAYBC', payment_method_code: str = 'CC',
        payment_status_code: str = PaymentStatus.CREATED.value,
        invoice_number: str = None,
        payment_account_id: str = None,
        invoice_amount=0,
        paid_usd_amount=0
):
    """Return Factory."""
    payment: Payment = Payment(
        payment_system_code=payment_system_code,
        payment_method_code=payment_method_code,
        payment_status_code=payment_status_code,
        invoice_number=invoice_number,
        payment_account_id=payment_account_id,
        invoice_amount=invoice_amount,
        paid_usd_amount=paid_usd_amount
    )
    return payment


def factory_routing_slip(
        number: str = None,
        payment_account_id=None,
        status: str = RoutingSlipStatus.ACTIVE.value,
        total: int = 0,
        remaining_amount: Decimal = 0.0,
        routing_slip_date=datetime.now(tz=timezone.utc)
):
    """Return Factory."""
    routing_slip: RoutingSlip = RoutingSlip(
        number=number or fake.name(),
        payment_account_id=payment_account_id,
        status=status,
        total=total,
        remaining_amount=Decimal(str(remaining_amount)),
        created_by='test',
        routing_slip_date=routing_slip_date
    )
    return routing_slip


def factory_routing_slip_usd(
        number: str = None,
        payment_account_id=None,
        status: str = RoutingSlipStatus.ACTIVE.value,
        total: int = 0,
        remaining_amount: int = 0,
        routing_slip_date=datetime.now(tz=timezone.utc),
        total_usd=0
):
    """Return Factory."""
    routing_slip: RoutingSlip = RoutingSlip(
        number=number or fake.name(),
        payment_account_id=payment_account_id,
        status=status,
        total=total,
        remaining_amount=Decimal(str(remaining_amount)),
        created_by='test',
        routing_slip_date=routing_slip_date,
        total_usd=total_usd
    )
    return routing_slip


def factory_invoice(payment_account, status_code: str = InvoiceStatus.CREATED.value,
                    corp_type_code='CP',
                    business_identifier: str = 'CP0001234',
                    service_fees: float = 0.0,
                    total=0,
                    paid=None,
                    payment_method_code: str = PaymentMethod.DIRECT_PAY.value,
                    created_on: datetime = datetime.now(tz=timezone.utc),
                    routing_slip=None,
                    folio_number=1234567890,
                    created_name='test name',
                    details=[{'label': 'label', 'value': 'value'}]):
    """Return Factory."""
    return Invoice(
        invoice_status_code=status_code,
        payment_account_id=payment_account.id,
        total=total,
        paid=paid,
        created_by='test',
        created_name=created_name,
        created_on=created_on,
        business_identifier=business_identifier,
        corp_type_code=corp_type_code,
        folio_number=folio_number,
        service_fees=service_fees,
        bcol_account=payment_account.bcol_account,
        payment_method_code=payment_method_code,
        routing_slip=routing_slip,
        details=details
    )


def factory_payment_line_item(invoice_id: str, fee_schedule_id: int, filing_fees: int = 10, total: int = 10,
                              service_fees: int = 0, status: str = LineItemStatus.ACTIVE.value,
                              description: str = None):
    """Return Factory."""
    return PaymentLineItem(
        invoice_id=invoice_id,
        fee_schedule_id=fee_schedule_id,
        filing_fees=filing_fees,
        total=total,
        service_fees=service_fees,
        line_item_status_code=status,
        fee_distribution_id=DistributionCode.find_by_active_for_fee_schedule(fee_schedule_id).distribution_code_id,
        description=description
    )


def factory_payment_transaction(
        payment_id: str,
        status_code: str = 'CREATED',
        client_system_url: str = 'http://google.com/',
        pay_system_url: str = 'http://google.com',
        transaction_start_time: datetime = datetime.now(tz=timezone.utc),
        transaction_end_time: datetime = datetime.now(tz=timezone.utc),
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


def factory_receipt(
        invoice_id: int,
        receipt_number: str = 'TEST1234567890',
        receipt_date: datetime = datetime.now(tz=timezone.utc),
        receipt_amount: float = 10.0
):
    """Return Factory."""
    return Receipt(
        invoice_id=invoice_id,
        receipt_number=receipt_number,
        receipt_date=receipt_date,
        receipt_amount=receipt_amount
    )


def factory_statement_settings(
        frequency: str = 'WEEKLY',
        payment_account_id: str = None,
        from_date: datetime = datetime.now(tz=timezone.utc),
        to_date: datetime = None):
    """Return Factory."""
    return StatementSettings(frequency=frequency,
                             payment_account_id=payment_account_id,
                             from_date=from_date,
                             to_date=to_date).save()


def factory_statement(
        frequency: str = 'WEEKLY',
        payment_account_id: str = None,
        from_date: datetime = datetime.now(tz=timezone.utc),
        to_date: datetime = datetime.now(tz=timezone.utc),
        statement_settings_id: str = None,
        created_on: datetime = datetime.now(tz=timezone.utc)):
    """Return Factory."""
    return Statement(frequency=frequency,
                     statement_settings_id=statement_settings_id,
                     payment_account_id=payment_account_id,
                     from_date=from_date,
                     to_date=to_date,
                     created_on=created_on).save()


def factory_statement_invoices(
        statement_id: str,
        invoice_id: str):
    """Return Factory."""
    return StatementInvoices(statement_id=statement_id,
                             invoice_id=invoice_id).save()


def activate_pad_account(auth_account_id: str):
    """Activate the pad account."""
    payment_account: PaymentAccount = PaymentAccount.find_by_auth_account_id(auth_account_id)
    payment_account.pad_activation_date = datetime.now(tz=timezone.utc)
    payment_account.save()
    cfs_account = CfsAccount.find_effective_by_payment_method(payment_account.id, PaymentMethod.PAD.value)
    cfs_account.status = 'ACTIVE'
    cfs_account.save()


def get_paybc_transaction_request():
    """Return a stub payment transaction request."""
    return {
        'clientSystemUrl': 'http://localhost:8080/abcd',
        'payReturnUrl': 'http://localhost:8081/xyz'
    }


def get_auth_staff(method_of_payment='CC'):
    """Return authorization response for staff users."""
    return {
        'orgMembership': 'OWNER',
        'roles': [
            'view',
            'edit',
            'make_payment',
            'staff'
        ],
        'business': {
            'folioNumber': 'MOCK1234',
            'name': 'Mock Business'
        },
        'account': {
            'accountType': 'BASIC',
            'id': '1234',
            'name': 'Mock Account',
            'paymentInfo': {
                'methodOfPayment': 'INTERNAL'
            }
        }
    }


def get_auth_basic_user(method_of_payment='CC'):
    """Return authorization response for basic users."""
    return {
        'orgMembership': 'OWNER',
        'roles': [
            'view',
            'edit',
            'make_payment'
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
                'methodOfPayment': method_of_payment,
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
            'edit',
            'make_payment'
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
        'name': 'Test Memo Line',
        'projectCode': '1111111',
        'responsibilityCentre': '22222',
        'stob': '9000',
        'serviceLine': '20244',
        'startDate': '2020-07-29'
    }


def get_distribution_schedules_payload():
    """Return distribution schedule payload."""
    return [{
        'feeScheduleId': 1
    }]


def get_basic_account_payload(payment_method: str = PaymentMethod.DIRECT_PAY.value):
    """Return a basic payment account object."""
    return {
        'accountId': 1234,
        'accountName': 'Test Account',
        'paymentInfo': {
            'methodOfPayment': payment_method,
            'billable': True
        }
    }


def get_premium_account_payload(payment_method: str = PaymentMethod.DRAWDOWN.value,
                                account_id: int = randrange(999999)):
    """Return a premium payment account object."""
    return {
        'accountId': account_id,
        'accountName': 'Test Account',
        'branchName': 'Test Branch',
        'bcolAccountNumber': '1000000',
        'bcolUserId': 'U100000',
        'paymentInfo': {
            'methodOfPayment': payment_method,
            'billable': True
        }
    }


def get_eft_enable_account_payload(payment_method: str = PaymentMethod.DRAWDOWN.value,
                                   account_id: int = randrange(999999)):
    """Return a premium eft enable payment account object."""
    return {
        'accountId': account_id,
        'accountName': 'Test Account',
        'bcolAccountNumber': '2000000',
        'bcolUserId': 'U100000',
        'eft_enable': False,
        'paymentInfo': {
            'methodOfPayment': payment_method,
            'billable': True
        }
    }


def get_pad_account_payload(account_id: int = randrange(999999), bank_number: str = '001', transit_number='999',
                            bank_account='1234567890'):
    """Return a pad payment account object."""
    return {
        'accountId': account_id,
        'accountName': 'Test Account',
        'bcolAccountNumber': '1000000',
        'bcolUserId': 'U100000',
        'paymentInfo': {
            'methodOfPayment': PaymentMethod.PAD.value,
            'billable': True,
            'bankTransitNumber': transit_number,
            'bankInstitutionNumber': bank_number,
            'bankAccountNumber': bank_account
        }
    }


def get_unlinked_pad_account_payload(account_id: int = randrange(999999), bank_number: str = '001',
                                     transit_number='999',
                                     bank_account='1234567890'):
    """Return a pad payment account object."""
    return {
        'accountId': account_id,
        'accountName': 'Test Account',
        'paymentInfo': {
            'methodOfPayment': PaymentMethod.PAD.value,
            'billable': True,
            'bankTransitNumber': transit_number,
            'bankInstitutionNumber': bank_number,
            'bankAccountNumber': bank_account
        }
    }


def get_gov_account_payload(payment_method: str = PaymentMethod.EJV.value,
                            account_id: int = randrange(999999), project_code='1111111', billable: bool = True):
    """Return a gov account payload."""
    return {
        'accountId': account_id,
        'accountName': 'Test Account',
        'paymentInfo': {
            'methodOfPayment': payment_method,
            'billable': billable,
            'revenueAccount': {
                'client': '100',
                'projectCode': project_code,
                'responsibilityCentre': '22222',
                'serviceLine': '1111111',
                'stob': '9000'
            }
        }
    }


def get_gov_account_payload_with_no_revenue_account(payment_method: str = PaymentMethod.EJV.value,
                                                    account_id: int = randrange(999999)):
    """Return a gov account payload with no revenue account."""
    return {
        'accountId': account_id,
        'accountName': 'Test Account',
        'paymentInfo': {
            'methodOfPayment': payment_method,
            'billable': False
        }
    }


def get_routing_slip_request(
        number: str = '206380875',
        cheque_receipt_numbers: List[Tuple] = [('1234567890', PaymentMethod.CHEQUE.value, 100)]
):
    """Return a routing slip request dictionary."""
    routing_slip_payload: Dict[str, any] = {
        'number': number,
        'routingSlipDate': datetime.now(tz=timezone.utc).strftime(DT_SHORT_FORMAT),
        'paymentAccount': {
            'accountName': 'TEST'
        },
        'payments': []
    }
    for cheque_detail in cheque_receipt_numbers:
        routing_slip_payload['payments'].append({
            'paymentMethod': cheque_detail[1],
            'paymentDate': datetime.now(tz=timezone.utc).strftime(DT_SHORT_FORMAT),
            'chequeReceiptNumber': cheque_detail[0],
            'paidAmount': cheque_detail[2]
        })

    return routing_slip_payload


def factory_comments(routing_slip_number: str, username: str = 'comment_user', comment: str = 'test_comment'):
    """Return a routing slip request dictionary."""
    comment = Comment(submitter_name=username,
                      routing_slip_number=routing_slip_number,
                      comment=comment
                      )
    return comment


def factory_eft_file(file_ref: str = 'test_ref.txt'):
    """Return an EFT file model."""
    return EFTFile(file_ref=file_ref).save()


def factory_eft_shortname(short_name: str):
    """Return an EFT short name model."""
    return EFTShortnames(short_name=short_name)


def factory_eft_shortname_link(short_name_id: int, auth_account_id: str = '1234',
                               updated_by: str = None, updated_on: datetime = datetime.now()):
    """Return an EFT short name link model."""
    return EFTShortnameLinks(
        eft_short_name_id=short_name_id,
        auth_account_id=auth_account_id,
        status_code=EFTShortnameStatus.PENDING.value,
        updated_by=updated_by,
        updated_by_name=updated_by,
        updated_on=updated_on
    )


def factory_non_sufficient_funds(invoice_id: int, invoice_number: str, description: str = None):
    """Return a Non-Sufficient Funds Model."""
    return NonSufficientFundsModel(invoice_id=invoice_id, invoice_number=invoice_number, description=description)


def factory_distribution_code(name: str, client: str = '111', reps_centre: str = '22222', service_line: str = '33333',
                              stob: str = '4444', project_code: str = '5555555', service_fee_dist_id: int = None,
                              disbursement_dist_id: int = None):
    """Return Factory."""
    return DistributionCode(name=name,
                            client=client,
                            responsibility_centre=reps_centre,
                            service_line=service_line,
                            stob=stob,
                            project_code=project_code,
                            service_fee_distribution_code_id=service_fee_dist_id,
                            disbursement_distribution_code_id=disbursement_dist_id,
                            start_date=datetime.today().date(),
                            created_by='test')


def factory_distribution_link(distribution_code_id: int, fee_schedule_id: int):
    """Return Factory."""
    return DistributionCodeLink(fee_schedule_id=fee_schedule_id,
                                distribution_code_id=distribution_code_id)
