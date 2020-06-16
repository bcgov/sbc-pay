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

from bcol_api.exceptions import BusinessException, PaymentException
from bcol_api.services.bcol_soap import BcolSoap
from bcol_api.utils.errors import Error


class BcolPayment:  # pylint:disable=too-few-public-methods
    """Service to manage BCOL Payments."""

    def create_payment(self, pay_request: Dict):
        """Create payment record in BCOL."""
        current_app.logger.debug('<create_payment')
        padded_amount = self._pad_zeros(pay_request.get('amount', '0'))
        # Call the query profile service to fetch profile
        data = {
            'Version': current_app.config.get('BCOL_DEBIT_ACCOUNT_VERSION'),
            'Feecode': pay_request.get('feeCode'),
            'Userid': pay_request.get('userId'),
            'Key': pay_request.get('invoiceNumber'),
            'Account': '',
            'RateType': '',
            'Folio': pay_request.get('folioNumber', None),
            'FormNumber': pay_request.get('formNumber', ''),
            'Quantity': pay_request.get('quantity', ''),
            'Rate': padded_amount,
            'Amount': padded_amount,
            'Remarks': pay_request.get('remarks', 'BCOL Payment from BCROS'),
            'RedundantFlag': pay_request.get('reduntantFlag', ' '),
            'linkcode': current_app.config.get('BCOL_LINK_CODE')
        }
        try:
            response = self.debit_account(data)
            current_app.logger.debug(response)

            if self.__get(response, 'ReturnCode') != '0000':
                raise BusinessException(Error.PAYMENT_ERROR)

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

        except zeep.exceptions.Fault as fault:
            current_app.logger.error(fault)
            parsed_fault_detail = BcolSoap().get_payment_client().wsdl.types.deserialize(fault.detail[0])
            current_app.logger.error(parsed_fault_detail)
            raise PaymentException(message=self.__get(parsed_fault_detail, 'message'),
                                   code=self.__get(parsed_fault_detail, 'returnCode'))
        except BusinessException as e:
            raise e
        except Exception as e:
            current_app.logger.error(e)
            raise BusinessException(Error.PAYMENT_ERROR)

        current_app.logger.debug('>query_profile')
        return pay_response

    def __get(self, value: object, key: object) -> str:  # pragma: no cover # pylint: disable=no-self-use
        """Get the value from dict and strip."""
        if value and value[key]:
            return value[key].strip() if isinstance(value[key], str) else value[key]
        return None

    def debit_account(self, data: Dict):  # pragma: no cover # pylint: disable=no-self-use
        """Debit BCOL account."""
        client = BcolSoap().get_payment_client()
        return zeep.helpers.serialize_object(client.service.debitAccount(req=data))

    def _pad_zeros(self, amount: str = '0'):  # pylint: disable=no-self-use
        """Pad the amount with Zeroes to make sure the string is 10 chars."""
        if not amount:
            return None
        amount = int(float(amount) * 100)  # Multiply with 100, as for e.g, 50.00 needs to be 5000
        return str(amount).zfill(10)
