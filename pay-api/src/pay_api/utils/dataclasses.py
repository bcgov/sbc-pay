# Copyright © 2025 Province of British Columbia
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
"""Data classes."""
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PurchaseHistorySearch:
    """Purchase History search input parameters."""

    auth_account_id: str
    search_filter: Dict
    page: int
    limit: int
    filter_by_product: bool = False
    allowed_products: List[str] = None
    return_all: bool = False
    max_no_records: int = 0
