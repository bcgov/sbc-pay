# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Service to invoke CFS related operations."""
import base64
import re
from collections import defaultdict
from http import HTTPStatus
from typing import Any, Dict, List, Tuple

from flask import current_app
from requests import HTTPError

from pay_api.exceptions import ServiceUnavailableException
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.constants import (
    CFS_ADJ_ACTIVITY_NAME, CFS_BATCH_SOURCE, CFS_CASH_RCPT, CFS_CM_BATCH_SOURCE, CFS_CMS_TRX_TYPE, CFS_CUST_TRX_TYPE,
    CFS_CUSTOMER_PROFILE_CLASS, CFS_DRAWDOWN_BALANCE, CFS_FAS_CUSTOMER_PROFILE_CLASS, CFS_LINE_TYPE,
    CFS_NSF_REVERSAL_REASON, CFS_PAYMENT_REVERSAL_REASON, CFS_RCPT_EFT_WIRE, CFS_TERM_NAME, DEFAULT_ADDRESS_LINE_1,
    DEFAULT_CITY, DEFAULT_COUNTRY, DEFAULT_CURRENCY, DEFAULT_JURISDICTION, DEFAULT_POSTAL_CODE)
from pay_api.utils.enums import AuthHeaderType, ContentType, PaymentMethod, PaymentSystem, ReverseOperation
from pay_api.utils.util import current_local_time, generate_transaction_number


class CFSService(OAuthService):
    """Service to invoke CFS related operations."""

    @classmethod
    def create_cfs_account(cls, identifier: str, contact_info: Dict[str, Any],  # pylint: disable=too-many-arguments
                           payment_info: Dict[str, any] = None,
                           receipt_method: str = None, site_name=None, is_fas: bool = False) -> Dict[str, str]:
        """Create a cfs account and return the details."""
        current_app.logger.info(f'Creating CFS Customer Profile Details for : {identifier}')
        party_id = f"{current_app.config.get('CFS_PARTY_PREFIX')}{identifier}"
        access_token = CFSService.get_token().json().get('access_token')
        party = CFSService._create_party(access_token, party_id)
        account = CFSService._create_paybc_account(access_token, party, is_fas)
        site = CFSService._create_site(access_token, account, contact_info, receipt_method, site_name, is_fas)
        account_details = {
            'party_number': party.get('party_number'),
            'account_number': account.get('account_number'),
            'site_number': site.get('site_number')
        }
        if payment_info:
            account_details.update(cls._save_bank_details(access_token, party.get('party_number'),
                                                          account.get('account_number'),
                                                          site.get('site_number'), payment_info))

        return account_details

    @staticmethod
    def get_site(cfs_account: CfsAccountModel) -> Dict[str, any]:
        """Get the site details."""
        access_token = CFSService.get_token().json().get('access_token')
        cfs_base: str = current_app.config.get('CFS_BASE_URL')
        site_url = f'{cfs_base}/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}/' \
                   f'sites/{cfs_account.cfs_site}/'
        site_response = OAuthService.get(site_url, access_token, AuthHeaderType.BEARER, ContentType.JSON)
        return site_response.json()

    @staticmethod
    def update_site_receipt_method(cfs_account: CfsAccountModel, receipt_method: str):
        """Update the receipt method for the site."""
        access_token = CFSService.get_token().json().get('access_token')
        pad_stop_payload = {
            'receipt_method': receipt_method
        }
        cfs_base: str = current_app.config.get('CFS_BASE_URL')
        site_url = f'{cfs_base}/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}/' \
                   f'sites/{cfs_account.cfs_site}/'
        site_update_response = OAuthService.post(site_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                                 pad_stop_payload, is_put=True)
        return site_update_response.json()

    @staticmethod
    def validate_bank_account(bank_details: Tuple[Dict[str, Any]]) -> Dict[str, str]:
        """Validate bank details by invoking CFS validation Service."""
        current_app.logger.debug('<Validating bank account details')
        validation_url = current_app.config.get('CFS_BASE_URL') + '/cfs/validatepayins/'
        bank_number = str(bank_details.get('bankInstitutionNumber', None))
        branch_number = str(bank_details.get('bankTransitNumber', None))
        bank_details: Dict[str, str] = {
            'accountNumber': bank_details.get('bankAccountNumber', None),
            'branchNumber': f'{branch_number:0>5}',
            'bankNumber': f'{bank_number:0>4}',
        }
        try:
            access_token = CFSService.get_token().json().get('access_token')

            # raise_for_error should be false so that HTTPErrors are not thrown.PAYBC sends validation errors as 404
            bank_validation_response_obj = OAuthService.post(validation_url, access_token, AuthHeaderType.BEARER,
                                                             ContentType.JSON,
                                                             bank_details, raise_for_error=False)

            if bank_validation_response_obj.status_code in (HTTPStatus.OK.value, HTTPStatus.BAD_REQUEST.value):
                bank_validation_response = bank_validation_response_obj.json()
                validation_response = {
                    'bank_number': bank_validation_response.get('bank_number', None),
                    'bank_name': bank_validation_response.get('bank_number', None),
                    'branch_number': bank_validation_response.get('branch_number', None),
                    'transit_address': bank_validation_response.get('transit_address', None),
                    'account_number': bank_validation_response.get('account_number', None),
                    'is_valid': bank_validation_response.get('CAS-Returned-Messages', None) == 'VALID',
                    'status_code': HTTPStatus.OK.value,
                    'message': CFSService._transform_error_message(
                        bank_validation_response.get('CAS-Returned-Messages'))
                }
            else:
                current_app.logger.debug('<Bank validation HTTP exception- {}', bank_validation_response_obj.text)
                validation_response = {
                    'status_code': bank_validation_response_obj.status_code,
                    'message': ['Bank validation service cant be reached']
                }

        except ServiceUnavailableException as exc:  # suppress all other errors
            current_app.logger.debug('<Bank validation ServiceUnavailableException exception- {}', exc.error)
            validation_response = {
                'status_code': HTTPStatus.SERVICE_UNAVAILABLE.value,
                'message': [str(exc.error)]
            }

        return validation_response

    @staticmethod
    def _create_party(access_token: str = None, party_name: str = None):
        """Create a party record in PayBC."""
        current_app.logger.debug('<Creating party Record')
        party_url = current_app.config.get('CFS_BASE_URL') + '/cfs/parties/'
        party: Dict[str, Any] = {
            'customer_name': party_name
        }

        party_response = OAuthService.post(party_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, party)
        current_app.logger.debug('>Creating party Record')
        return party_response.json()

    @staticmethod
    def _transform_error_message(param: str) -> str:
        """Strip out unwanted characters from the CFS returned error message."""
        # [-+]?[0-9]+ -  matches the CFS format of 0001 -  etc.
        list_messages = re.split('[-+]?[0-9]+ - ', param)
        # strip out first empty
        stripped_message = list(filter(None, list_messages))
        return stripped_message

    @staticmethod
    def _create_paybc_account(access_token, party, is_fas: bool):
        """Create account record in PayBC."""
        current_app.logger.debug('<Creating CFS account')
        account_url = current_app.config.get('CFS_BASE_URL') + f"/cfs/parties/{party.get('party_number', None)}/accs/"
        account: Dict[str, Any] = {
            'account_description': current_app.config.get('CFS_ACCOUNT_DESCRIPTION'),
            'customer_profile_class': CFS_FAS_CUSTOMER_PROFILE_CLASS if is_fas else CFS_CUSTOMER_PROFILE_CLASS
        }

        account_response = OAuthService.post(account_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                             account)
        current_app.logger.debug('>Creating CFS account')
        return account_response.json()

    @staticmethod
    def _create_site(access_token, account, contact_info, receipt_method,  # pylint: disable=too-many-arguments
                     site_name=None, is_fas: bool = False):
        """Create site in PayBC."""
        current_app.logger.debug('<Creating CFS site ')
        if not contact_info:
            contact_info = {}
        site_url = current_app.config.get(
            'CFS_BASE_URL') + f"/cfs/parties/{account.get('party_number', None)}" \
                              f"/accs/{account.get('account_number', None)}/sites/"
        country = get_non_null_value(contact_info.get('country'), DEFAULT_COUNTRY)
        province_tag = 'province' if country == DEFAULT_COUNTRY else 'state'
        site: Dict[str, Any] = {
            'site_name': site_name or 'Site 1',  # Make it dynamic if we ever need multiple sites per account
            'city': get_non_null_value(contact_info.get('city'), DEFAULT_CITY),
            'address_line_1': get_non_null_value(contact_info.get('addressLine1'), DEFAULT_ADDRESS_LINE_1),
            'postal_code': get_non_null_value(contact_info.get('postalCode'), DEFAULT_POSTAL_CODE).replace(' ', ''),
            province_tag: get_non_null_value(contact_info.get('province'), DEFAULT_JURISDICTION),
            'country': country,
            'customer_site_id': '1',
            'primary_bill_to': 'Y',
            'customer_profile_class': CFS_FAS_CUSTOMER_PROFILE_CLASS if is_fas else CFS_CUSTOMER_PROFILE_CLASS
        }
        if receipt_method:
            site['receipt_method'] = receipt_method

        try:
            site_response = OAuthService.post(site_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                              site).json()
        except HTTPError as e:
            # If the site creation fails with 400, query and return site
            if e.response.status_code == 400:
                site_response = \
                    OAuthService.get(site_url, access_token, AuthHeaderType.BEARER, ContentType.JSON).json().get(
                        'items')[0]
            else:
                raise e
        current_app.logger.debug('>Creating CFS site ')
        return site_response

    @classmethod
    def _save_bank_details(cls, access_token, party_number: str,  # pylint: disable=too-many-arguments
                           account_number: str,
                           site_number: str, payment_info: Dict[str, str]):
        """Save bank details to the site."""
        current_app.logger.debug('<Creating CFS payment details ')
        site_payment_url = current_app.config.get(
            'CFS_BASE_URL') + f'/cfs/parties/{party_number}/accs/{account_number}/sites/{site_number}/payment/'

        bank_number = str(payment_info.get('bankInstitutionNumber'))
        branch_number = str(payment_info.get('bankTransitNumber'))

        # bank account name should match legal name
        name = re.sub(r'[^a-zA-Z0-9]+', ' ', payment_info.get('bankAccountName', ''))

        payment_details: Dict[str, str] = {
            'bank_account_name': name[:30],
            'bank_number': f'{bank_number:0>4}',
            'branch_number': f'{branch_number:0>5}',
            'bank_account_number': str(payment_info.get('bankAccountNumber')),
            'country_code': DEFAULT_COUNTRY,
            'currency_code': DEFAULT_CURRENCY
        }
        site_payment_response = OAuthService.post(site_payment_url, access_token, AuthHeaderType.BEARER,
                                                  ContentType.JSON,
                                                  payment_details).json()

        payment_details = {
            'bank_account_number': payment_info.get('bankAccountNumber'),
            'bank_number': bank_number,
            'bank_branch_number': branch_number,
            'payment_instrument_number': site_payment_response.get('payment_instrument_number')
        }

        current_app.logger.debug('>Creating CFS payment details')
        return payment_details

    @classmethod
    def get_invoice(cls, cfs_account: CfsAccountModel, inv_number: str):
        """Get invoice from CFS."""
        current_app.logger.debug(f'<Getting invoice from CFS : {inv_number}')
        access_token: str = CFSService.get_token().json().get('access_token')
        invoice_url = current_app.config.get(
            'CFS_BASE_URL') + f'/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}/' \
                              f'sites/{cfs_account.cfs_site}/invs/{inv_number}/'

        invoice_response = CFSService.get(invoice_url, access_token, AuthHeaderType.BEARER, ContentType.JSON)
        return invoice_response.json()

    @classmethod
    def reverse_rs_receipt_in_cfs(cls, cfs_account, receipt_number, operation: ReverseOperation):
        """Reverse Receipt."""
        current_app.logger.debug('>Reverse receipt: %s', receipt_number)
        access_token: str = CFSService.get_token(PaymentSystem.FAS).json().get('access_token')
        cfs_base: str = current_app.config.get('CFS_BASE_URL')
        receipt_url = f'{cfs_base}/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}' \
                      f'/sites/{cfs_account.cfs_site}/rcpts/{receipt_number}/reverse'
        current_app.logger.debug('Receipt URL %s', receipt_url)
        payload = {
            'reversal_reason': CFS_NSF_REVERSAL_REASON if operation == ReverseOperation.NSF.value
            else CFS_PAYMENT_REVERSAL_REASON,
            'reversal_comment': cls._build_reversal_comment(operation)
        }
        return CFSService.post(receipt_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, payload)

    @classmethod
    def apply_receipt(cls, cfs_account: CfsAccountModel, receipt_number: str, invoice_number: str) -> Dict[str, any]:
        """Apply Invoice to Routing slip receipt from CFS."""
        return cls._modify_rs_receipt_in_cfs(cfs_account, invoice_number, receipt_number)

    @classmethod
    def unapply_receipt(cls, cfs_account: CfsAccountModel, receipt_number: str, invoice_number: str) -> Dict[str, any]:
        """Unapply Invoice to Routing slip receipt from CFS."""
        return cls._modify_rs_receipt_in_cfs(cfs_account, invoice_number, receipt_number, verb='unapply')

    @classmethod
    def _modify_rs_receipt_in_cfs(cls, cfs_account, invoice_number, receipt_number, verb='apply'):
        """Apply and unapply using the verb passed."""
        current_app.logger.debug('>%s receipt: %s invoice:%s', verb, receipt_number, invoice_number)
        access_token: str = CFSService.get_token().json().get('access_token')
        cfs_base: str = current_app.config.get('CFS_BASE_URL')
        receipt_url = f'{cfs_base}/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}' \
                      f'/sites/{cfs_account.cfs_site}/rcpts/{receipt_number}/{verb}'
        current_app.logger.debug('Receipt URL %s', receipt_url)
        payload = {
            'invoice_number': invoice_number,
        }
        return CFSService.post(receipt_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, payload)

    @classmethod
    def update_bank_details(cls, name: str, party_number: str,  # pylint: disable=too-many-arguments
                            account_number: str, site_number: str,
                            payment_info: Dict[str, str]):
        """Update bank details to the site."""
        current_app.logger.debug('<Update bank details ')
        access_token = CFSService.get_token().json().get('access_token')
        payment_info['bankAccountName'] = name
        return cls._save_bank_details(access_token, party_number, account_number, site_number, payment_info)

    @staticmethod
    def get_token(payment_system=PaymentSystem.PAYBC):
        """Generate oauth token from PayBC/FAS which will be used for all communication."""
        current_app.logger.debug('<Getting token')
        token_url = current_app.config.get('CFS_BASE_URL', None) + '/oauth/token'
        match payment_system:
            case PaymentSystem.PAYBC:
                client_id = current_app.config.get('CFS_CLIENT_ID')
                secret = current_app.config.get('CFS_CLIENT_SECRET')
            case PaymentSystem.FAS:
                client_id = current_app.config.get('CFS_FAS_CLIENT_ID')
                secret = current_app.config.get('CFS_FAS_CLIENT_SECRET')
            case _:
                raise ValueError('Invalid Payment System')
        basic_auth_encoded = base64.b64encode(
            bytes(client_id + ':' + secret,
                  'utf-8')).decode('utf-8')
        data = 'grant_type=client_credentials'
        token_response = OAuthService.post(token_url, basic_auth_encoded, AuthHeaderType.BASIC,
                                           ContentType.FORM_URL_ENCODED, data)
        current_app.logger.debug('>Getting token')
        return token_response

    @classmethod
    def create_account_invoice(cls, transaction_number: str, line_items: List[PaymentLineItemModel],
                               cfs_account: CfsAccountModel) \
            -> Dict[str, any]:
        """Create CFS Account Invoice."""
        now = current_local_time()
        curr_time = now.strftime('%Y-%m-%dT%H:%M:%SZ')

        invoice_url = current_app.config.get(
            'CFS_BASE_URL') + f'/cfs/parties/{cfs_account.cfs_party}' \
                              f'/accs/{cfs_account.cfs_account}/sites/{cfs_account.cfs_site}/invs/'

        invoice_payload = {
            'batch_source': CFS_BATCH_SOURCE,
            'cust_trx_type': CFS_CUST_TRX_TYPE,
            'transaction_date': curr_time,
            'transaction_number': generate_transaction_number(transaction_number),
            'gl_date': curr_time,
            'term_name': CFS_TERM_NAME,
            'comments': '',
            'lines': cls.build_lines(line_items)
        }

        access_token = CFSService.get_token().json().get('access_token')
        invoice_response = CFSService.post(invoice_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                           invoice_payload)
        return invoice_response.json()

    @classmethod
    def _build_reversal_comment(cls, operation: ReverseOperation):
        """Build the comment for the reversal."""
        return {
            ReverseOperation.NSF.value: 'Non Sufficient Fund',
            ReverseOperation.LINK.value: 'Linking Routing Slip',
            ReverseOperation.VOID.value: 'Created In Error',
            ReverseOperation.CORRECTION.value: 'Corrected In Revision'
        }.get(operation)

    @classmethod
    def build_lines(cls, payment_line_items: List[PaymentLineItemModel], negate: bool = False):
        """Build lines for the invoice."""
        # Fetch all distribution codes to reduce DB hits. Introduce caching if needed later
        distribution_codes: List[DistributionCodeModel] = DistributionCodeModel.find_all()
        lines_map = defaultdict(dict)  # To group all the lines with same GL code together.
        index: int = 0
        for line_item in payment_line_items:
            # Find the distribution from the above list
            distribution_code = [dist for dist in distribution_codes if
                                 dist.distribution_code_id == line_item.fee_distribution_id][0] \
                if line_item.fee_distribution_id else None

            if line_item.total > 0:
                # Check if a line with same GL code exists, if YES just add up the amount. if NO, create a new line.
                line = lines_map[distribution_code.distribution_code_id]

                if not line:
                    index = index + 1
                    distribution = [{
                        'dist_line_number': index,
                        'amount': cls._get_amount(line_item.total, negate),
                        'account': f'{distribution_code.client}.{distribution_code.responsibility_centre}.'
                        f'{distribution_code.service_line}.{distribution_code.stob}.'
                        f'{distribution_code.project_code}.000000.0000'
                    }] if distribution_code else None

                    line = {
                        'line_number': index,
                        'line_type': CFS_LINE_TYPE,
                        'description': line_item.description,
                        'unit_price': cls._get_amount(line_item.total, negate),
                        'quantity': 1,
                        'distribution': distribution
                    }
                else:
                    # Add up the price and distribution
                    line['unit_price'] = line['unit_price'] + cls._get_amount(line_item.total, negate)
                    line['distribution'][0]['amount'] = line['distribution'][0]['amount'] + \
                        cls._get_amount(line_item.total, negate)

                lines_map[distribution_code.distribution_code_id] = line

            if line_item.service_fees > 0:
                service_fee_distribution: DistributionCodeModel = DistributionCodeModel.find_by_id(
                    distribution_code.service_fee_distribution_code_id)
                service_line = lines_map[service_fee_distribution.distribution_code_id]

                if not service_line:
                    index = index + 1
                    service_line = {
                        'line_number': index,
                        'line_type': CFS_LINE_TYPE,
                        'description': 'Service Fee',
                        'unit_price': cls._get_amount(line_item.service_fees, negate),
                        'quantity': 1,
                        'distribution': [
                            {
                                'dist_line_number': index,
                                'amount': cls._get_amount(line_item.service_fees, negate),
                                'account': f'{service_fee_distribution.client}.'
                                           f'{service_fee_distribution.responsibility_centre}.'
                                           f'{service_fee_distribution.service_line}.'
                                           f'{service_fee_distribution.stob}.'
                                           f'{service_fee_distribution.project_code}.000000.0000'
                            }
                        ]
                    }

                else:
                    # Add up the price and distribution
                    service_line['unit_price'] = service_line['unit_price'] + \
                                                               cls._get_amount(line_item.service_fees, negate)
                    service_line['distribution'][0]['amount'] = service_line['distribution'][0]['amount'] + \
                        cls._get_amount(line_item.service_fees, negate)
                lines_map[service_fee_distribution.distribution_code_id] = service_line
        return list(lines_map.values())

    @classmethod
    def _get_amount(cls, amount, negate):
        return -amount if negate else amount

    @staticmethod
    def reverse_invoice(inv_number: str):
        """Adjust the invoice to zero."""
        current_app.logger.info(f'Reverse CFS Invoice : {inv_number}')
        access_token: str = CFSService.get_token().json().get('access_token')
        cfs_base: str = current_app.config.get('CFS_BASE_URL')
        invoice_url = f'{cfs_base}/cfs/parties/invs/{inv_number}/creditbalance/'

        CFSService.post(invoice_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, {})

    @classmethod
    def add_nsf_adjustment(cls, cfs_account: CfsAccountModel, inv_number: str, amount: float):
        """Add adjustment to the invoice."""
        current_app.logger.debug('>Creating NSF Adjustment for Invoice: %s', inv_number)
        access_token: str = CFSService.get_token().json().get('access_token')
        cfs_base: str = current_app.config.get('CFS_BASE_URL')
        adjustment_url = f'{cfs_base}/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}/sites/' \
                         f'{cfs_account.cfs_site}/invs/{inv_number}/adjs/'
        current_app.logger.debug('Adjustment URL %s', adjustment_url)

        adjustment = {
            'comment': 'Non sufficient funds charge for rejected PAD Payment',
            'lines': [
                {
                    'line_number': '1',
                    'adjustment_amount': str(amount),
                    'activity_name': 'BC Registries - NSF Charge'
                }
            ]
        }

        adjustment_response = cls.post(adjustment_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                       adjustment)

        current_app.logger.debug('>Created CFS Invoice NSF Adjustment')
        return adjustment_response.json()

    @classmethod
    def adjust_invoice(cls, cfs_account: CfsAccountModel, inv_number: str, amount=0.0, adjustment_lines=None):
        """Add adjustment to the invoice."""
        current_app.logger.debug('>Creating Adjustment for Invoice: %s', inv_number)
        access_token: str = CFSService.get_token().json().get('access_token')
        cfs_base: str = current_app.config.get('CFS_BASE_URL')
        adjustment_url = f'{cfs_base}/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}/sites/' \
                         f'{cfs_account.cfs_site}/invs/{inv_number}/adjs/'
        current_app.logger.debug('Adjustment URL %s', adjustment_url)

        adjustment = {
            'comment': 'Invoice cancellation',
            'lines': adjustment_lines or [
                {
                    'line_number': '1',
                    'adjustment_amount': str(amount),
                    'activity_name': CFS_ADJ_ACTIVITY_NAME
                }
            ]
        }

        adjustment_response = cls.post(adjustment_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                       adjustment)

        current_app.logger.debug('>Created Invoice Adjustment')
        return adjustment_response.json()

    @staticmethod
    def create_cfs_receipt(cfs_account: CfsAccountModel,  # pylint:disable=too-many-arguments
                           rcpt_number: str,
                           rcpt_date: str,
                           amount: float,
                           payment_method: str,
                           access_token: str = None) -> Dict[str, str]:
        """Create Eft Wire receipt for the account."""
        current_app.logger.debug(f'<create_cfs_receipt : {cfs_account}, {rcpt_number}, {amount}, {payment_method}')

        access_token: str = access_token or CFSService.get_token().json().get('access_token')
        cfs_base: str = current_app.config.get('CFS_BASE_URL')
        receipt_url = f'{cfs_base}/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}/' \
                      f'sites/{cfs_account.cfs_site}/rcpts/'

        if payment_method == PaymentMethod.DRAWDOWN.value:
            cfs_payment_method = CFS_DRAWDOWN_BALANCE
        elif payment_method in (PaymentMethod.CASH.value, PaymentMethod.CHEQUE.value):
            cfs_payment_method = CFS_CASH_RCPT
        else:
            cfs_payment_method = CFS_RCPT_EFT_WIRE
        payload = {
            'receipt_number': rcpt_number,
            'receipt_date': rcpt_date,
            'receipt_amount': str(amount),
            'payment_method': cfs_payment_method,
            'comments': ''
        }
        current_app.logger.debug('>create_cfs_receipt')
        return CFSService.post(receipt_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, payload).json()

    @classmethod
    def get_receipt(cls, cfs_account: CfsAccountModel, receipt_number: str) -> Dict[str, any]:
        """Return receipt details from CFS."""
        current_app.logger.debug('>Getting receipt: %s', receipt_number)
        access_token: str = CFSService.get_token().json().get('access_token')
        cfs_base: str = current_app.config.get('CFS_BASE_URL')
        receipt_url = f'{cfs_base}/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}' \
                      f'/sites/{cfs_account.cfs_site}/rcpts/{receipt_number}/'
        current_app.logger.debug('Receipt URL %s', receipt_url)

        receipt_response = cls.get(receipt_url, access_token, AuthHeaderType.BEARER, ContentType.JSON)

        current_app.logger.debug('>Received receipt response')
        return receipt_response.json()

    @classmethod
    def get_cms(cls, cfs_account: CfsAccountModel, cms_number: str) -> Dict[str, any]:
        """Return CMS details from CFS."""
        current_app.logger.debug('>Getting CMS: %s', cms_number)
        access_token: str = CFSService.get_token().json().get('access_token')
        cfs_base: str = current_app.config.get('CFS_BASE_URL')
        cms_url = f'{cfs_base}/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}' \
                  f'/sites/{cfs_account.cfs_site}/cms/{cms_number}/'
        current_app.logger.debug('CMS URL %s', cms_url)

        cms_response = cls.get(cms_url, access_token, AuthHeaderType.BEARER, ContentType.JSON)

        current_app.logger.debug('>Received CMS response')
        return cms_response.json()

    @classmethod
    def create_cms(cls, line_items: List[PaymentLineItemModel], cfs_account: CfsAccountModel) -> Dict[str, any]:
        """Create CM record in CFS."""
        current_app.logger.debug('>Creating CMS')
        access_token: str = CFSService.get_token().json().get('access_token')
        cfs_base: str = current_app.config.get('CFS_BASE_URL')
        cms_url = f'{cfs_base}/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}' \
                  f'/sites/{cfs_account.cfs_site}/cms/'
        current_app.logger.debug('CMS URL %s', cms_url)

        now = current_local_time()
        curr_time = now.strftime('%Y-%m-%dT%H:%M:%SZ')

        cms_payload = {
            'batch_source': CFS_CM_BATCH_SOURCE,
            'cust_trx_type': CFS_CMS_TRX_TYPE,
            'transaction_date': curr_time,
            'gl_date': curr_time,
            'comments': '',
            'lines': cls.build_lines(line_items, negate=True)
        }

        cms_response = CFSService.post(cms_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, cms_payload)

        current_app.logger.debug('>Received CMS response')
        return cms_response.json()

    @classmethod
    def adjust_receipt_to_zero(cls, cfs_account: CfsAccountModel, receipt_number: str, is_refund: bool = False):
        """Adjust Receipt in CFS to bring it down to zero.

        1. Query the receipt and check if balance is more than zero.
        2. Adjust the receipt with activity name corresponding to refund or write off.
        """
        current_app.logger.debug('<adjust_receipt_to_zero: %s %s', cfs_account, receipt_number)
        access_token: str = CFSService.get_token(PaymentSystem.FAS).json().get('access_token')
        cfs_base: str = current_app.config.get('CFS_BASE_URL')
        receipt_url = f'{cfs_base}/cfs/parties/{cfs_account.cfs_party}/accs/{cfs_account.cfs_account}/' \
                      f'sites/{cfs_account.cfs_site}/rcpts/{receipt_number}/'
        adjustment_url = f'{receipt_url}adjustment'
        current_app.logger.debug('Receipt Adjustment URL %s', adjustment_url)

        receipt_response = cls.get(receipt_url, access_token, AuthHeaderType.BEARER, ContentType.JSON)
        current_app.logger.info(f"Balance on {receipt_number} - {receipt_response.json().get('unapplied_amount')}")
        if (unapplied_amount := float(receipt_response.json().get('unapplied_amount', 0))) > 0:
            adjustment = {
                'activity_name': 'Refund Adjustment FAS' if is_refund else 'Write-off Adjustment FAS',
                'adjustment_amount': str(unapplied_amount)
            }

            cls.post(adjustment_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, adjustment)
            receipt_response = cls.get(receipt_url, access_token, AuthHeaderType.BEARER, ContentType.JSON)
            current_app.logger.info(f"Balance on {receipt_number} - {receipt_response.json().get('unapplied_amount')}")

        current_app.logger.debug('>adjust_receipt_to_zero')


def get_non_null_value(value: str, default_value: str):
    """Return non null value for the value by replacing default value."""
    return default_value if (value is None or value.strip() == '') else value
