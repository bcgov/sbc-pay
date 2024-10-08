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
"""Constants."""
from enum import Enum
from typing import Dict


class Role(Enum):
    """Role enum."""

    STAFF = "staff"
    EDIT = "edit"
    ACCOUNT_HOLDER = "account_holder"
    SYSTEM = "system"


def auth_code_mapping() -> Dict:
    """Return Auth code mapping from BCOL."""
    return {
        "G": "GDSA",
        "M": "Master",
        "O": "Office",
        "P": "Prime",
        "C": "Contact",
        "": "Ordinary",
    }


def account_type_mapping() -> Dict:
    """Return Account type mapping from BCOL."""
    return {"B": "Billable", "N": "Non-Billable", "I": "Internal"}


def tax_status_mapping() -> Dict:
    """Return Tax status mapping from BCOL."""
    return {"E": "Exempt", "Z": "Zero-rate", "": "Must-Pay"}
