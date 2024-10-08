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

    INVALID_CREDENTIALS = (
        "Invalid Credentials",
        "Invalid User ID or Password",
        HTTPStatus.BAD_REQUEST,
    )
    NOT_A_PRIME_USER = (
        "Not a prime user.",
        "You must enter the PRIME CONTACT User ID and password for your BC Online account.",
        HTTPStatus.BAD_REQUEST,
    )
    SYSTEM_ERROR = (
        "BC Online is currently not available.",
        "BC Online is currently not available. Please try again later.",
        HTTPStatus.BAD_REQUEST,
    )
    PAYMENT_ERROR = (
        "Cannot create payment",
        "Error occurred during payment",
        HTTPStatus.BAD_REQUEST,
    )

    INVALID_REQUEST = "Invalid Request", "Invalid Request", HTTPStatus.BAD_REQUEST

    def __new__(cls, title, details, status):
        """Attributes for the enum."""
        obj = object.__new__(cls)
        obj.title = title
        obj.details = details
        obj.status = status
        return obj
