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
    PAY013 = 'Invalid redirect url', HTTPStatus.UNAUTHORIZED
    PAY014 = 'Fee override is not allowed', HTTPStatus.UNAUTHORIZED
    PAY015 = 'Premium account setup is incomplete', HTTPStatus.UNAUTHORIZED

    PAY020 = 'Invalid Account Number for the User', HTTPStatus.BAD_REQUEST
    PAY021 = 'Zero dollars deducted from BCOL', HTTPStatus.BAD_REQUEST

    PAY999 = 'Invalid Request', HTTPStatus.BAD_REQUEST
    SERVICE_UNAVAILABLE = 'Service Unavailable', HTTPStatus.BAD_REQUEST

    BCOL_UNAVAILABLE = 'BC Online system is not available', HTTPStatus.BAD_REQUEST
    BCOL_ACCOUNT_CLOSED = 'BC Online account has been closed', HTTPStatus.BAD_REQUEST
    BCOL_USER_REVOKED = 'BC Online user has been revoked', HTTPStatus.BAD_REQUEST
    BCOL_ACCOUNT_REVOKED = 'BC Online account is revoked', HTTPStatus.BAD_REQUEST
    BCOL_ERROR = 'Error occurred during BC Online transaction. Please contact help desk.', HTTPStatus.BAD_REQUEST

    def __new__(cls, message, status):
        """Attributes for the enum."""
        obj = object.__new__(cls)
        obj.message = message
        obj.status = status
        return obj


def get_bcol_error(error_code: int):
    """Return error code corresponding to BC Online error code."""
    error: Error = Error.BCOL_ERROR
    if error_code == 7:
        error = Error.BCOL_UNAVAILABLE
    elif error_code == 20:
        error = Error.BCOL_ACCOUNT_CLOSED
    elif error_code == 21:
        error = Error.BCOL_USER_REVOKED
    elif error_code == 48:
        error = Error.BCOL_ACCOUNT_REVOKED
    return error
