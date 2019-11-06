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

"""Tests to assure the BCOL service layer.

Test-Suite to ensure that the BCOL Service layer is working as expected.
"""

from bcol_api.services.bcol_soap import BcolSoap


def test_bcol_soap(app):
    """Test BCOL SOAP Initialization."""
    with app.app_context():
        bcol_soap = BcolSoap()
        assert bcol_soap is not None
        assert bcol_soap.get_profile_client() is not None
        assert bcol_soap.get_payment_client() is not None


def test_bcol_soap_multiple_instances(app):
    """Test BCOL SOAP Initialization for multiple instances."""
    with app.app_context():
        bcol_soap = BcolSoap()
        bcol_soap2 = BcolSoap()
        assert bcol_soap == bcol_soap2
