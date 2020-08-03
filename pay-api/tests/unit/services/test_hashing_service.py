# Copyright © 2019 Province of British Columbia
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

"""Tests to assure the HashingService service layer."""

from pay_api.services.hashing import HashingService


def test_encode_and_verify_success(session):  # pylint:disable=unused-argument
    """Test encode and verify the checksum."""
    param = 'Hello World'
    encode_string = HashingService.encode(param)
    assert HashingService.is_valid_checksum(param, encode_string) is True


def test_encode_and_verify_failure_random_string(session):  # pylint:disable=unused-argument
    """Test encoding and failure verification."""
    param = 'Hello World'
    param2 = 'some random strimg'
    encode_string = HashingService.encode(param)
    assert HashingService.is_valid_checksum(param2, encode_string) is False
