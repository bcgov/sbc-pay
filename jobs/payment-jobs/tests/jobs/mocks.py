# Copyright © 2022 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Mocks to help out with unit testing."""

from unittest.mock import Mock


def paybc_token_response(cls, *args):  # pylint: disable=unused-argument; mocks of library methods
    """Mock paybc token response."""
    return Mock(
        status_code=201,
        json=lambda: {
            "access_token": "5945-534534554-43534535",
            "token_type": "Basic",
            "expires_in": 3600,
        },
    )


def refund_payload_response(cls, *args, **kwargs):  # pylint: disable=unused-argument; mocks of library methods
    """Mock refund payload response."""
    return Mock(
        status_code=201,
        json=lambda: {
            "refundstatus": "PAID",
            "revenue": [
                {
                    "linenumber": "1",
                    "revenueaccount": "112.32041.35301.1278.3200000.000000.0000",
                    "revenueamount": "130",
                    "glstatus": "PAID",
                    "glerrormessage": None,
                    "refundglstatus": "RJCT",
                    "refundglerrormessage": "BAD",
                },
                {
                    "linenumber": "2",
                    "revenueaccount": "112.32041.35301.1278.3200000.000000.0000",
                    "revenueamount": "1.5",
                    "glstatus": "PAID",
                    "glerrormessage": None,
                    "refundglstatus": "RJCT",
                    "refundglerrormessage": "BAD",
                },
            ],
        },
    )


def empty_refund_payload_response(cls, *args):  # pylint: disable=unused-argument; mocks of library methods
    """Mock empty refund payload response."""
    return Mock(status_code=201, json=lambda: {})


def mocked_invoice_response(cls, *args):  # pylint: disable=unused-argument; mocks of library methods
    """Mock POST invoice 200 payload response."""
    return Mock(
        status_code=200,
        json=lambda: {
            "invoice_number": "123",
            "pbc_ref_number": "10007",
            "party_number": "104894",
            "account_number": "116225",
            "site_number": "179145",
            "total": "15",
            "amount_due": "15",
        },
    )
