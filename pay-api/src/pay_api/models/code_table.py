# Copyright © 2024 Province of British Columbia
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
"""Base class for code model."""


class CodeTable:  # pylint: disable=too-few-public-methods
    """This class provides base methods for Code Table."""

    @classmethod
    def find_by_code(cls, code):
        """Given a code, this will return code master details."""
        code_table = cls.query.filter_by(code=code).one_or_none()  # pylint: disable=no-member
        return code_table

    @classmethod
    def find_all(cls):
        """Return all of the code master details."""
        codes = cls.query.all()  # pylint: disable=no-member
        return codes
