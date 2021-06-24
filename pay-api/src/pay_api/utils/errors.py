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

    INVALID_CORP_OR_FILING_TYPE = 'INVALID_CORP_OR_FILING_TYPE', HTTPStatus.BAD_REQUEST

    INVALID_PAYMENT_ID = 'INVALID_PAYMENT_ID', HTTPStatus.BAD_REQUEST

    INVALID_TRANSACTION = 'INVALID_TRANSACTION', HTTPStatus.BAD_REQUEST

    INVALID_REDIRECT_URI = 'INVALID_REDIRECT_URI', HTTPStatus.BAD_REQUEST

    INVALID_TRANSACTION_ID = 'INVALID_TRANSACTION_ID', HTTPStatus.BAD_REQUEST

    INVALID_ACCOUNT_ID = 'INVALID_ACCOUNT_ID', HTTPStatus.BAD_REQUEST

    COMPLETED_PAYMENT = 'COMPLETED_PAYMENT', HTTPStatus.BAD_REQUEST

    ACCOUNT_IN_PAD_CONFIRMATION_PERIOD = 'ACCOUNT_IN_PAD_CONFIRMATION_PERIOD', HTTPStatus.BAD_REQUEST

    CANCELLED_PAYMENT = 'CANCELLED_PAYMENT', HTTPStatus.BAD_REQUEST

    INVALID_INVOICE_ID = 'INVALID_INVOICE_ID', HTTPStatus.BAD_REQUEST

    FEE_OVERRIDE_NOT_ALLOWED = 'FEE_OVERRIDE_NOT_ALLOWED', HTTPStatus.UNAUTHORIZED

    INCOMPLETE_ACCOUNT_SETUP = 'INCOMPLETE_ACCOUNT_SETUP', HTTPStatus.UNAUTHORIZED

    BCOL_UNAVAILABLE = 'BCOL_UNAVAILABLE', HTTPStatus.BAD_REQUEST
    BCOL_ACCOUNT_CLOSED = 'BCOL_ACCOUNT_CLOSED', HTTPStatus.BAD_REQUEST
    BCOL_USER_REVOKED = 'BCOL_USER_REVOKED', HTTPStatus.BAD_REQUEST
    BCOL_ACCOUNT_REVOKED = 'BCOL_ACCOUNT_REVOKED', HTTPStatus.BAD_REQUEST
    BCOL_ACCOUNT_INSUFFICIENT_FUNDS = 'BCOL_ACCOUNT_INSUFFICIENT_FUNDS', HTTPStatus.BAD_REQUEST
    BCOL_ERROR = 'BCOL_ERROR', HTTPStatus.BAD_REQUEST

    SERVICE_UNAVAILABLE = 'SERVICE_UNAVAILABLE', HTTPStatus.SERVICE_UNAVAILABLE
    INVALID_REQUEST = 'INVALID_REQUEST', HTTPStatus.BAD_REQUEST, 'Invalid Request'

    DIRECT_PAY_INVALID_RESPONSE = 'DIRECT_PAY_INVALID_RESPONSE', HTTPStatus.BAD_REQUEST

    ACCOUNT_EXISTS = 'ACCOUNT_EXISTS', HTTPStatus.BAD_REQUEST

    OUTSTANDING_CREDIT = 'OUTSTANDING_CREDIT', HTTPStatus.BAD_REQUEST
    TRANSACTIONS_IN_PROGRESS = 'TRANSACTIONS_IN_PROGRESS', HTTPStatus.BAD_REQUEST
    FROZEN_ACCOUNT = 'FROZEN_ACCOUNT', HTTPStatus.BAD_REQUEST

    def __new__(cls, code, status, message=None, details=None):
        """Attributes for the enum."""
        obj = object.__new__(cls)
        obj.code = code
        obj.status = status
        obj.message = message
        obj.details = details if details else message
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
    elif error_code == 61:
        error = Error.BCOL_ACCOUNT_INSUFFICIENT_FUNDS
    return error
