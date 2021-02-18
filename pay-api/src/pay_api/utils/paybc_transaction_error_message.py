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
    'PLEASE TRY AGAIN': 'PLEASE_TRY_AGAIN',
    'DECLINED': 'DECLINED',
    'Invalid Card Number': 'INVALID_CARD_NUMBER',
    'Application Error - Sending Request': 'APPLICATION_ERROR_SENDING_REQUEST',
    'Call for Auth': 'CALL_FOR_AUTH',
    'Transaction timeout - No available device': 'TRANSACTION_TIMEOUT_NO_DEVICE',
    'Response from Beanstream is invalid due to modifications of parameters sent': 'BEANSTREAM_INVALID_RESPONSE',
    'Validation Error': 'VALIDATION_ERROR',
    'Payment Canceled': 'PAYMENT_CANCELLED',
    'Duplicate Order Number - This order number has already been processed': 'DUPLICATE_ORDER_NUMBER',
    'Approved': 'APPROVED',
    'Decline': 'DECLINED',
    'Declined EXPIRED CARD': 'DECLINED_EXPIRED_CARD',
}
