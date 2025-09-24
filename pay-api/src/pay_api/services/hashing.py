# Copyright © 2024 Province of British Columbia
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


"""Service for hashing."""

import hashlib

from flask import current_app


class HashingService:
    """Hashing Service class."""

    @staticmethod
    def encode(param: str) -> str:
        """Return a hashed string using the static salt from config."""
        current_app.logger.debug(f"encoding for string {param}")
        api_key = current_app.config.get("PAYBC_DIRECT_PAY_API_KEY")
        # MD5 required for PayBC API compatibility - not used for cryptographic security
        return hashlib.md5(f"{param}{api_key}".encode()).hexdigest()  # noqa: S324

    @staticmethod
    def is_valid_checksum(param: str, hash_val: str) -> bool:
        """Validate if the checksum matches."""
        api_key = current_app.config.get("PAYBC_DIRECT_PAY_API_KEY")
        # MD5 required for PayBC API compatibility - not used for cryptographic security
        return hashlib.md5(f"{param}{api_key}".encode()).hexdigest() == hash_val  # noqa: S324
