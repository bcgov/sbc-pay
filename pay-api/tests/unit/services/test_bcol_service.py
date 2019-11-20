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

from pay_api.services.bcol_service import BcolService


QUERY_PROFILE_RESPONSE = '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/ " ' \
                         'xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/ " ' \
                         'xmlns:xsd="http://www.w3.org/2001/XMLSchema "' \
                         ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><soapenv:Header/>' \
                         '<soapenv:Body><p32:queryProfileResponse ' \
                         'xmlns:p32="http://queryprofile.webservices.bconline.gov.bc.ca"><p32:queryProfileReturn>' \
                         '<p32:Userid>PB25020</p32:Userid><p32:Date xsi:nil="true"/><p32:Time xsi:nil="true"/>' \
                         '<p32:AccountNumber>1234567890</p32:AccountNumber><p32:AuthCode>M</p32:AuthCode>' \
                         '<p32:AuthDate>' \
                         '</p32:AuthDate><p32:AccountType>B</p32:AccountType><p32:GSTStatus></p32:GSTStatus>' \
                         '<p32:PSTStatus></p32:PSTStatus><p32:UserName>Test, Test</p32:UserName><p32:Address>' \
                         '<p32:AddressA>#400A - 4000 SEYMOUR PLACE</p32:AddressA><p32:AddressB>PENTHOUSE' \
                         '</p32:AddressB>' \
                         '<p32:City>AB1</p32:City><p32:Prov>BC</p32:Prov><p32:Country>CANADA</p32:Country>' \
                         '<p32:PostalCode>V8X 5J8</p32:PostalCode></p32:Address>' \
                         '<p32:UserPhone>(250)953-8271 EX1999</p32:UserPhone><p32:UserFax>(250)953-8212' \
                         '</p32:UserFax>' \
                         '<p32:Status>Y</p32:Status><p32:org-name>BC ONLINE TECHNICAL TEAM DEVL</p32:org-name>' \
                         '<p32:org-type>LAW</p32:org-type><p32:originator xsi:nil="true"/>' \
                         '<p32:queryProfileFlag name="OSBR"></p32:queryProfileFlag>' \
                         '<p32:queryProfileFlag name="ADS">' \
                         '</p32:queryProfileFlag><p32:queryProfileFlag name="COLIN_TYPE"></p32:queryProfileFlag>' \
                         '<p32:queryProfileFlag name="COMP"></p32:queryProfileFlag></p32:queryProfileReturn>' \
                         '</p32:queryProfileResponse></soapenv:Body></soapenv:Envelope>'


# def test_query_profile(app):
#    """Test query profile service."""
#    with app.app_context():
#        mock_query_profile = patch('pay_api.services.bcol_service.BcolService._invoke_bcol_query_profile')
#        response = QUERY_PROFILE_RESPONSE
#        mock_get = mock_query_profile.start()
#        mock_get.return_value = Mock(status_code=200)
#        mock_get.return_value.json.return_value = response

#        query_profile_response = BcolService().query_profile('TEST', 'TEST')

#        mock_query_profile.stop()

#        assert query_profile_response.json().get('userId') == 'PB25020'


def test_service_methods(app):
    """Test service methods."""
    with app.app_context():
        bcol_service = BcolService()
        assert bcol_service.create_account(None, None) is None
        assert bcol_service.create_invoice(None, None, None) is None
        assert bcol_service.get_payment_system_url(None, None, None) is None
        assert bcol_service.get_payment_system_code() == 'BCOL'
        assert bcol_service.update_invoice(None, None, None, None) is None
        assert bcol_service.cancel_invoice(None, None) is None
        assert bcol_service.get_receipt(None, None, None) is None
