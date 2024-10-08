# Copyright © 2023 Province of British Columbia
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
"""EFT Enum definitions."""
from enum import Enum


class EFTConstants(Enum):
    """EFT constants."""

    # Currency
    CURRENCY_CAD = "CAD"

    # Record Type
    HEADER_RECORD_TYPE = "1"
    TRANSACTION_RECORD_TYPE = "2"
    TRAILER_RECORD_TYPE = "7"

    # Formats
    DATE_TIME_FORMAT = "%Y%m%d%H%M"
    DATE_FORMAT = "%Y%m%d"

    # Lengths
    EXPECTED_LINE_LENGTH = 140
