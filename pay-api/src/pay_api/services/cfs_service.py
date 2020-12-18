# Copyright © 2019 Province of British Columbia
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
from http import HTTPStatus
from typing import Any, Dict, List, Tuple

from flask import current_app
from requests import HTTPError

from pay_api.exceptions import ServiceUnavailableException
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import CfsAccount as CfsAccountModel

from pay_api.services.oauth_service import OAuthService
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.constants import (
    CFS_BATCH_SOURCE, CFS_CUSTOMER_PROFILE_CLASS, CFS_CUST_TRX_TYPE, CFS_LINE_TYPE, CFS_TERM_NAME,
    DEFAULT_ADDRESS_LINE_1,
    DEFAULT_CITY, DEFAULT_COUNTRY, DEFAULT_CURRENCY, DEFAULT_JURISDICTION, DEFAULT_POSTAL_CODE,
    RECEIPT_METHOD_PAD_STOP, RECEIPT_METHOD_PAD_DAILY, CFS_RCPT_EFT_WIRE, CFS_CMS_TRX_TYPE, CFS_CM_BATCH_SOURCE)
from pay_api.utils.enums import (
    AuthHeaderType, ContentType)
from pay_api.utils.util import current_local_time, generate_transaction_number


class CFSService(OAuthService):
    """Service to invoke CFS related operations."""

    @classmethod
    def create_cfs_account(cls, name: str, contact_info: Dict[str, Any],
                           payment_info: Dict[str, any] = None, receipt_method: str = None) -> Dict[str, str]:
        """Create a cfs account and return the details."""
        name = re.sub(r'[^a-zA-Z0-9]+', ' ', name)
        access_token = CFSService.get_token().json().get('access_token')
        party = CFSService._create_party(access_token, name)
        account = CFSService._create_paybc_account(access_token, party)
        site = CFSService._create_site(access_token, account, contact_info, receipt_method)
        account_details = {
            'party_number': party.get('party_number'),
            'account_number': account.get('account_number'),
            'site_number': site.get('site_number')
        }
        if payment_info:
            account_details.update(cls._save_bank_details(access_token, name, party.get('party_number'),
                                                          account.get('account_number'),
                                                          site.get('site_number'), payment_info))

        return account_details

    @classmethod
    def suspend_cfs_account(cls, cfs_account: CfsAccountModel) -> Dict[str, any]:
        """Suspend a CFS PAD Account from any further PAD transactions."""
        return cls._update_site(cfs_account, receipt_method=RECEIPT_METHOD_PAD_STOP)

    @classmethod
    def unsuspend_cfs_account(cls, cfs_account: CfsAccountModel) -> Dict[str, any]:
        """Unuspend a CFS PAD Account from any further PAD transactions."""
        return cls._update_site(cfs_account, receipt_method=RECEIPT_METHOD_PAD_DAILY)

    @classmethod
    def _update_site(cls, cfs_account: CfsAccountModel, receipt_method: str):
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
        bank_details: Dict[str, str] = {
            'accountNumber': bank_details.get('bankAccountNumber', None),
            'branchNumber': bank_details.get('bankTransitNumber', None),
            'bankNumber': bank_details.get('bankInstitutionNumber', None),
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
                    'message': 'Bank validation service cant be reached'
                }

        except ServiceUnavailableException as exc:  # suppress all other errors
            current_app.logger.debug('<Bank validation ServiceUnavailableException exception- {}', exc.error)
            validation_response = {
                'status_code': HTTPStatus.SERVICE_UNAVAILABLE.value,
                'message': str(exc.error)
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
    def _create_paybc_account(access_token, party):
        """Create account record in PayBC."""
        current_app.logger.debug('<Creating account')
        account_url = current_app.config.get('CFS_BASE_URL') + '/cfs/parties/{}/accs/'.format(
            party.get('party_number', None))
        account: Dict[str, Any] = {
            'account_description': current_app.config.get('CFS_ACCOUNT_DESCRIPTION'),
            'customer_profile_class': CFS_CUSTOMER_PROFILE_CLASS
        }

        account_response = OAuthService.post(account_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                             account)
        current_app.logger.debug('>Creating account')
        return account_response.json()

    @staticmethod
    def _create_site(access_token, account, contact_info, receipt_method):
        """Create site in PayBC."""
        current_app.logger.debug('<Creating site ')
        if not contact_info:
            contact_info = {}
        site_url = current_app.config.get('CFS_BASE_URL') + '/cfs/parties/{}/accs/{}/sites/' \
            .format(account.get('party_number', None), account.get('account_number', None))
        site: Dict[str, Any] = {
            'site_name': 'Site 1',  # Make it dynamic if we ever need multiple sites per account
            'city': get_non_null_value(contact_info.get('city'), DEFAULT_CITY),
            'address_line_1': get_non_null_value(contact_info.get('addressLine1'), DEFAULT_ADDRESS_LINE_1),
            'postal_code': get_non_null_value(contact_info.get('postalCode'), DEFAULT_POSTAL_CODE).replace(' ', ''),
            'province': get_non_null_value(contact_info.get('province'), DEFAULT_JURISDICTION),
            'country': get_non_null_value(contact_info.get('country'), DEFAULT_COUNTRY),
            'customer_site_id': '1',
            'primary_bill_to': 'Y',
            'customer_profile_class': CFS_CUSTOMER_PROFILE_CLASS
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
        current_app.logger.debug('>Creating site ')
        return site_response

    @classmethod
    def _save_bank_details(cls, access_token, name: str, party_number: str,  # pylint: disable=too-many-arguments
                           account_number: str,
                           site_number: str, payment_info: Dict[str, str]):
        """Save bank details to the site."""
        current_app.logger.debug('<Creating payment details ')
        site_payment_url = current_app.config.get(
            'CFS_BASE_URL') + f'/cfs/parties/{party_number}/accs/{account_number}/sites/{site_number}/payment/'

        payment_details: Dict[str, str] = {
            'bank_account_name': name,
            'bank_number': str(payment_info.get('bankInstitutionNumber')),
            'branch_number': str(payment_info.get('bankTransitNumber')),
            'bank_account_number': str(payment_info.get('bankAccountNumber')),
            'country_code': DEFAULT_COUNTRY,
            'currency_code': DEFAULT_CURRENCY
        }
        site_payment_response = OAuthService.post(site_payment_url, access_token, AuthHeaderType.BEARER,
                                                  ContentType.JSON,
                                                  payment_details).json()

        payment_details = {
            'bank_account_number': payment_info.get('bankAccountNumber'),
            'bank_number': payment_info.get('bankInstitutionNumber'),
            'bank_branch_number': payment_info.get('bankTransitNumber'),
            'payment_instrument_number': site_payment_response.get('payment_instrument_number')
        }

        current_app.logger.debug('>Creating payment details')
        return payment_details

    @classmethod
    def update_bank_details(cls, name: str, party_number: str,  # pylint: disable=too-many-arguments
                            account_number: str, site_number: str,
                            payment_info: Dict[str, str]):
        """Update bank details to the site."""
        current_app.logger.debug('<Update bank details ')
        access_token = CFSService.get_token().json().get('access_token')
        return cls._save_bank_details(access_token, name, party_number, account_number, site_number, payment_info)

    @staticmethod
    def get_token():
        """Generate oauth token from payBC which will be used for all communication."""
        current_app.logger.debug('<Getting token')
        token_url = current_app.config.get('CFS_BASE_URL', None) + '/oauth/token'
        basic_auth_encoded = base64.b64encode(
            bytes(current_app.config.get('CFS_CLIENT_ID') + ':' + current_app.config.get('CFS_CLIENT_SECRET'),
                  'utf-8')).decode('utf-8')
        data = 'grant_type=client_credentials'
        token_response = OAuthService.post(token_url, basic_auth_encoded, AuthHeaderType.BASIC,
                                           ContentType.FORM_URL_ENCODED, data)
        current_app.logger.debug('>Getting token')
        return token_response

    @classmethod
    def create_account_invoice(cls, transaction_number: str, line_items: List[PaymentLineItemModel], payment_account) \
            -> Dict[str, any]:
        """Create CFS Account Invoice."""
        now = current_local_time()
        curr_time = now.strftime('%Y-%m-%dT%H:%M:%SZ')

        invoice_url = current_app.config.get('CFS_BASE_URL') + '/cfs/parties/{}/accs/{}/sites/{}/invs/' \
            .format(payment_account.cfs_party, payment_account.cfs_account, payment_account.cfs_site)

        invoice_payload = dict(
            batch_source=CFS_BATCH_SOURCE,
            cust_trx_type=CFS_CUST_TRX_TYPE,
            transaction_date=curr_time,
            transaction_number=generate_transaction_number(transaction_number),
            gl_date=curr_time,
            term_name=CFS_TERM_NAME,
            comments='',
            lines=cls._build_lines(line_items)
        )

        access_token = CFSService.get_token().json().get('access_token')
        invoice_response = CFSService.post(invoice_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                           invoice_payload)
        return invoice_response

    @classmethod
    def _build_lines(cls, payment_line_items: List[PaymentLineItemModel], negate: bool = False):
        """Build lines for the invoice."""
        # Fetch all distribution codes to reduce DB hits. Introduce caching if needed later
        distribution_codes: List[DistributionCodeModel] = DistributionCodeModel.find_all()
        lines = []
        index: int = 0
        for line_item in payment_line_items:
            # Find the distribution from the above list
            distribution_code = [dist for dist in distribution_codes if
                                 dist.distribution_code_id == line_item.fee_distribution_id][0] \
                if line_item.fee_distribution_id else None
            index = index + 1
            distribution = [dict(
                dist_line_number=index,
                amount=cls._get_amount(line_item.total, negate),
                account=f'{distribution_code.client}.{distribution_code.responsibility_centre}.'
                        f'{distribution_code.service_line}.{distribution_code.stob}.'
                        f'{distribution_code.project_code}.000000.0000'
            )] if distribution_code else None
            lines.append(
                {
                    'line_number': index,
                    'line_type': CFS_LINE_TYPE,
                    'description': line_item.description,
                    'unit_price': cls._get_amount(line_item.total, negate),
                    'quantity': 1,
                    'attribute1': line_item.invoice_id,
                    'attribute2': line_item.id,
                    'distribution': distribution
                }
            )

            if line_item.service_fees > 0:
                index = index + 1
                lines.append(
                    {
                        'line_number': index,
                        'line_type': CFS_LINE_TYPE,
                        'description': 'Service Fee',
                        'unit_price': cls._get_amount(line_item.service_fees, negate),
                        'quantity': 1,
                        'attribute1': line_item.invoice_id,
                        'attribute2': line_item.id,
                        'distribution': [
                            {
                                'dist_line_number': index,
                                'amount': cls._get_amount(line_item.service_fees, negate),
                                'account': f'{distribution_code.service_fee_client}.'
                                           f'{distribution_code.service_fee_responsibility_centre}.'
                                           f'{distribution_code.service_fee_line}.'
                                           f'{distribution_code.service_fee_stob}.'
                                           f'{distribution_code.service_fee_project_code}.000000.0000'
                            }
                        ]
                    }
                )

        return lines

    @classmethod
    def _get_amount(cls, amount, negate):
        return -amount if negate else amount

    @staticmethod
    def reverse_invoice(inv_number: str):
        """Adjust the invoice to zero."""
        current_app.logger.debug('<paybc_service_Getting token')
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

        adjustment = dict(
            comment='Non sufficient funds charge for rejected PAD Payment',
            lines=[
                {
                    'line_number': '1',
                    'adjustment_amount': str(amount),
                    'activity_name': 'BC Registries - NSF Charge'
                }
            ]
        )

        adjustment_response = cls.post(adjustment_url, access_token, AuthHeaderType.BEARER, ContentType.JSON,
                                       adjustment)

        current_app.logger.debug('>Created CFS Invoice NSF Adjustment')
        return adjustment_response.json()

    @staticmethod
    def create_eft_wire_receipt(payment_account: PaymentAccount,
                                rcpt_number: str,
                                rcpt_date: str,
                                amount: float) -> Dict[str, str]:
        """Create Eft Wire receipt for the account."""
        current_app.logger.debug('<create_credits')
        access_token: str = CFSService.get_token().json().get('access_token')
        cfs_base: str = current_app.config.get('CFS_BASE_URL')
        receipt_url = f'{cfs_base}/cfs/parties/{payment_account.cfs_party}/accs/{payment_account.cfs_account}/' \
                      f'sites/{payment_account.cfs_site}/rcpts/'

        payload = {
            'receipt_number': rcpt_number,
            'receipt_date': rcpt_date,
            'receipt_amount': str(amount),
            'payment_method': CFS_RCPT_EFT_WIRE,
            'comments': ''
        }

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

        cms_payload = dict(
            batch_source=CFS_CM_BATCH_SOURCE,
            cust_trx_type=CFS_CMS_TRX_TYPE,
            transaction_date=curr_time,
            gl_date=curr_time,
            comments='',
            lines=cls._build_lines(line_items, negate=True)
        )

        cms_response = CFSService.post(cms_url, access_token, AuthHeaderType.BEARER, ContentType.JSON, cms_payload)

        current_app.logger.debug('>Received CMS response')
        return cms_response.json()


def get_non_null_value(value: str, default_value: str):
    """Return non null value for the value by replacing default value."""
    return default_value if (value is None or value.strip() == '') else value
