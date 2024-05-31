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
"""Error definitions."""

PAYBC_TRANSACTION_ERROR_MESSAGE_DICT = {
    # code , value. the value is used by UI to do the mapping.
    # maps message from paybc to a code.
    'PLEASE TRY AGAIN': 'PLEASE_TRY_AGAIN',
    'DECLINED': 'DECLINED',
    'INVALID CARD NUMBER': 'INVALID_CARD_NUMBER',
    'APPLICATION ERROR - SENDING REQUEST': 'APPLICATION_ERROR_SENDING_REQUEST',
    'CALL FOR AUTH': 'CALL_FOR_AUTH',
    'TRANSACTION TIMEOUT - NO AVAILABLE DEVICE': 'TRANSACTION_TIMEOUT_NO_DEVICE',
    'RESPONSE FROM BEANSTREAM IS INVALID DUE TO MODIFICATIONS OF PARAMETERS SENT': 'BEANSTREAM_INVALID_RESPONSE',
    'VALIDATION ERROR': 'VALIDATION_ERROR',
    'PAYMENT CANCELED': 'PAYMENT_CANCELLED',
    'DUPLICATE ORDER NUMBER - THIS ORDER NUMBER HAS ALREADY BEEN PROCESSED': 'DUPLICATE_ORDER_NUMBER',
    'APPROVED': 'APPROVED',
    'DECLINE': 'DECLINED',
    'DECLINED EXPIRED CARD': 'DECLINED_EXPIRED_CARD',
}
