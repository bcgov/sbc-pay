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
from enum import Enum
from http import HTTPStatus


class Error(Enum):
    """Error Codes."""

    PAY001 = 'Invalid Corp Type or Filing Type', HTTPStatus.BAD_REQUEST
    PAY002 = 'No matching record found for Corp Type and Filing Type', HTTPStatus.BAD_REQUEST
    PAY003 = 'Cannot identify payment system, Invalid Corp Type or Payment Method', HTTPStatus.BAD_REQUEST
    PAY004 = 'Invalid Corp Number or Corp Type or Payment System Code', HTTPStatus.BAD_REQUEST
    PAY005 = 'Invalid Payment Identifier', HTTPStatus.BAD_REQUEST
    PAY006 = 'Transaction is already completed', HTTPStatus.BAD_REQUEST
    PAY007 = 'Invalid redirect uri', HTTPStatus.BAD_REQUEST
    PAY008 = 'Invalid transaction identifier', HTTPStatus.BAD_REQUEST
    PAY009 = 'Invalid account identifier', HTTPStatus.BAD_REQUEST
    PAY010 = 'Payment is already completed', HTTPStatus.BAD_REQUEST
    PAY011 = 'Payment is already cancelled', HTTPStatus.BAD_REQUEST
    PAY012 = 'Invalid invoice identifier', HTTPStatus.BAD_REQUEST
    PAY020 = 'Invalid Account Number for the User', HTTPStatus.BAD_REQUEST
    PAY021 = 'Zero dollars deducted from BCOL', HTTPStatus.BAD_REQUEST

    PAY999 = 'Invalid Request', HTTPStatus.BAD_REQUEST
    SERVICE_UNAVAILABLE = 'Service Unavailable', HTTPStatus.BAD_REQUEST

    def __new__(cls, message, status):
        """Attributes for the enum."""
        obj = object.__new__(cls)
        obj.message = message
        obj.status = status
        return obj
