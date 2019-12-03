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
"""Service to manage BCOL Payments."""

from typing import Dict

import zeep
from flask import current_app

from bcol_api.exceptions import BusinessException
from bcol_api.services.bcol_soap import BcolSoap
from bcol_api.utils.errors import Error


class BcolPayment:  # pylint:disable=too-few-public-methods
    """Service to manage BCOL Payments."""

    def create_payment(self, pay_request: Dict):
        """Create payment record in BCOL."""
        current_app.logger.debug('<create_payment')
        pay_response = None
        # Call the query profile service to fetch profile
        data = {
            'Version': current_app.config.get('BCOL_DEBIT_ACCOUNT_VERSION'),
            'Feecode': pay_request.get('feeCode'),
            'Userid': pay_request.get('userId'),
            'Key': pay_request.get('invoiceNumber'),
            'Account': '',
            'RateType': '',
            'Folio': pay_request.get('folioNumber'),
            'FormNumber': pay_request.get('formNumber', ''),
            'Quantity': pay_request.get('quantity', ''),
            'Rate': pay_request.get('rate', ''),
            'Amount': pay_request.get('amount', ''),
            'Remarks': pay_request.get('remarks', 'BCOL Payment from BCROS'),
            'RedundantFlag': pay_request.get('reduntantFlag', ' '),
            'linkcode': current_app.config.get('BCOL_LINK_CODE')
        }
        try:
            response = self.debit_account(data)
            current_app.logger.debug(response)

            if self.__get(response, 'ReturnCode') != '0000':
                raise BusinessException(Error.BCOL003)

            transaction = response['TranID']
            pay_response = {
                'statutoryFee': self.__get(response, 'StatFee'),
                'totalAmount': self.__get(response, 'Totamt'),
                'tsFee': self.__get(response, 'TSFee'),
                'gst': self.__get(response, 'Totgst'),
                'pst': self.__get(response, 'Totpst'),
                'accountNumber': self.__get(transaction, 'Account'),
                'userId': self.__get(transaction, 'UserID'),
                'date': self.__get(transaction, 'AppliedDate') + ':' + self.__get(transaction, 'AppliedTime'),
                'feeCode': self.__get(transaction, 'FeeCode'),
                'key': self.__get(transaction, 'Key'),
                'sequenceNo': self.__get(transaction, 'SequenceNo'),
            }

        except Exception as e:
            current_app.logger.error(e)
            raise BusinessException(Error.BCOL003)

        current_app.logger.debug('>query_profile')
        return pay_response

    def __get(self, value: object, key: object) -> str:  # pragma: no cover # pylint: disable=no-self-use
        """Get the value from dict and strip."""
        if value and value[key]:
            return value[key].strip()
        return None

    def debit_account(self, data: Dict):  # pragma: no cover # pylint: disable=no-self-use
        """Debit BCOL account."""
        client = BcolSoap().get_payment_client()
        return zeep.helpers.serialize_object(client.service.debitAccount(req=data))
