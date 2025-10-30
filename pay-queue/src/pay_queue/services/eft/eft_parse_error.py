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
"""Defines the structure of EFT Errors."""

from pay_queue.services.eft.eft_errors import EFTError


class EFTParseError:  # pylint: disable=too-few-public-methods
    """Defines the structure of a parse error when parsing an EFT File."""

    code: str
    message: str
    index: int

    def __init__(self, eft_error: EFTError, index: int = None) -> object:
        """Return an EFT Parse Error."""
        self.code = eft_error.name
        self.message = eft_error.value
        self.index = index
