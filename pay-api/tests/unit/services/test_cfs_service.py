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

"""Tests to assure the CFS service layer.

Test-Suite to ensure that the CFS Service layer is working as expected.
"""
from decimal import Decimal
from unittest.mock import patch

from requests import ConnectTimeout

from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.services.cfs_service import CFSService
from pay_api.utils.constants import TAX_CLASSIFICATION_GST
from tests.utilities.base_test import factory_distribution_code

cfs_service = CFSService()


def test_validate_bank_account_valid(session):
    """Test create_account."""
    input_bank_details = {
        "bankInstitutionNumber": "2001",
        "bankTransitNumber": "00720",
        "bankAccountNumber": "1234567",
    }
    with patch("pay_api.services.oauth_service.requests.post") as mock_post:
        mock_post.return_value.ok = True
        mock_post.return_value.status_code = 200
        valid_address = {
            "bank_number": "0001",
            "bank_name": "BANK OF MONTREAL",
            "branch_number": "00720",
            "transit_address": "DATA CENTRE,PRINCE ANDREW CENTRE,,DON MILLS,ON,M3C 2H4",
            "account_number": "1234567",
            "CAS-Returned-Messages": "VALID",
        }

        mock_post.return_value.json.return_value = valid_address

        bank_details = cfs_service.validate_bank_account(input_bank_details)
        assert bank_details.get("is_valid") is True
        assert bank_details.get("message")[0] == "VALID"
        assert bank_details.get("status_code") == 200


def test_validate_bank_account_invalid(session):
    """Test create_account."""
    input_bank_details = {
        "bankInstitutionNumber": "2001",
        "bankTransitNumber": "00720",
        "bankAccountNumber": "1234567",
    }
    with patch("pay_api.services.oauth_service.requests.post") as mock_post:
        # Configure the mock to return a response with an OK status code.
        mock_post.return_value.ok = True
        mock_post.return_value.status_code = 400
        valid_address = {
            "bank_number": "0001",
            "bank_name": "",
            "branch_number": "00720",
            "transit_address": "",
            "account_number": "1234787%876567",
            "CAS-Returned-Messages": "0003 - Account number has invalid characters."
            "0005 - Account number has non-numeric characters."
            "0006 - Account number length is not valid for this bank.",
        }

        mock_post.return_value.json.return_value = valid_address

        bank_details = cfs_service.validate_bank_account(input_bank_details)
        assert bank_details.get("is_valid") is False
        assert bank_details.get("message")[0] == "Account number has invalid characters."
        assert bank_details.get("message")[1] == "Account number has non-numeric characters."
        assert bank_details.get("message")[2] == "Account number length is not valid for this bank."
        assert bank_details.get("status_code") == 200


def test_validate_bank_account_exception(session):
    """Test create_account."""
    input_bank_details = {
        "bankInstitutionNumber": 111,
        "bankTransitNumber": 222,
        "bankAccountNumber": 33333333,
    }
    with patch(
        "pay_api.services.oauth_service.requests.post",
        side_effect=ConnectTimeout("mocked error"),
    ):
        bank_details = cfs_service.validate_bank_account(input_bank_details)
        assert bank_details.get("status_code") == 503
        assert "mocked error" in bank_details.get("message")


def test_ensure_totals_quantized(session):
    """Test payment line items that usually add up to bad float math."""
    distribution_code = DistributionCodeModel.find_by_id(1)
    distribution_code.service_fee_distribution_code_id = 1
    distribution_code.save()

    # Test values that would normally result in 1.4000000000000001 with float math
    payment_line_items = [
        PaymentLineItemModel(
            total=Decimal("0.3"),
            service_fees=Decimal("0.3"),
            fee_distribution_id=1,
            statutory_fees_gst=Decimal("0.00"),
            service_fees_gst=Decimal("0.00"),
        ),
        PaymentLineItemModel(
            total=Decimal("0.55"),
            service_fees=Decimal("0.55"),
            fee_distribution_id=1,
            statutory_fees_gst=Decimal("0.00"),
            service_fees_gst=Decimal("0.00"),
        ),
        PaymentLineItemModel(
            total=Decimal("0.55"),
            service_fees=Decimal("0.55"),
            fee_distribution_id=1,
            statutory_fees_gst=Decimal("0.00"),
            service_fees_gst=Decimal("0.00"),
        ),
    ]
    lines = cfs_service.build_lines(payment_line_items)  # pylint: disable=protected-access
    # Total: 1.4 (service fees) + 1.4 (filing fees) = 2.8
    assert float(lines[0]["unit_price"]) == 2.8


def _verify_line_structure(line, expected_price, expected_description=None, is_gst=False):
    """Verify a line has the expected structure and values."""
    assert float(line["unit_price"]) == float(expected_price)
    assert line["line_type"] == "LINE"

    if expected_description:
        assert line["description"] == expected_description

    if is_gst:
        assert line["tax_classification"] == TAX_CLASSIFICATION_GST

    if line.get("distribution"):
        account = line["distribution"][0]["account"]
        assert len(account.split(".")) == 7
        assert account.endswith(".000000.0000")


def test_build_lines_with_gst_fees(session):
    """Test build_lines with statutory and service fees GST."""
    base_distribution = factory_distribution_code(
        name="Base Distribution",
        client="111",
        reps_centre="11111",
        service_line="35300",
        stob="1230",
        project_code="1111110",
    )
    base_distribution.save()

    service_fee_distribution = factory_distribution_code(
        name="Service Fee Distribution",
        client="111",
        reps_centre="11111",
        service_line="35300",
        stob="1230",
        project_code="1111111",
    )
    service_fee_distribution.save()

    gst_statutory_distribution = factory_distribution_code(
        name="GST Statutory Distribution",
        client="111",
        reps_centre="11111",
        service_line="35300",
        stob="1230",
        project_code="1111112",
    )
    gst_statutory_distribution.save()

    gst_service_distribution = factory_distribution_code(
        name="GST Service Distribution",
        client="111",
        reps_centre="11111",
        service_line="35300",
        stob="1230",
        project_code="1111113",
    )
    gst_service_distribution.save()

    combined_gst_distribution = factory_distribution_code(
        name="Combined GST Distribution",
        client="111",
        reps_centre="11111",
        service_line="35300",
        stob="1230",
        project_code="1111115",
    )
    combined_gst_distribution.save()

    secondary_distribution = factory_distribution_code(
        name="Secondary Distribution",
        client="112",
        reps_centre="22222",
        service_line="35301",
        stob="1234",
        project_code="1111114",
    )
    secondary_distribution.save()

    base_distribution.service_fee_distribution_code_id = service_fee_distribution.distribution_code_id
    base_distribution.statutory_fees_gst_distribution_code_id = gst_statutory_distribution.distribution_code_id
    base_distribution.service_fee_gst_distribution_code_id = gst_service_distribution.distribution_code_id
    base_distribution.save()

    combined_gst_distribution.statutory_fees_gst_distribution_code_id = combined_gst_distribution.distribution_code_id
    combined_gst_distribution.service_fee_gst_distribution_code_id = combined_gst_distribution.distribution_code_id
    combined_gst_distribution.save()

    secondary_distribution.service_fee_distribution_code_id = service_fee_distribution.distribution_code_id
    secondary_distribution.statutory_fees_gst_distribution_code_id = gst_statutory_distribution.distribution_code_id
    secondary_distribution.service_fee_gst_distribution_code_id = gst_service_distribution.distribution_code_id
    secondary_distribution.save()

    payment_line_items = [
        PaymentLineItemModel(
            total=Decimal("100"),
            service_fees=Decimal("0"),
            fee_distribution_id=base_distribution.distribution_code_id,
            statutory_fees_gst=Decimal("5"),
            service_fees_gst=Decimal("0"),
            description="Base Filing Fee",
        ),
        PaymentLineItemModel(
            total=Decimal("0"),
            service_fees=Decimal("10"),
            fee_distribution_id=base_distribution.distribution_code_id,
            statutory_fees_gst=Decimal("0"),
            service_fees_gst=Decimal("0.50"),
            description="Service Fee",
        ),
        PaymentLineItemModel(
            total=Decimal("200"),
            service_fees=Decimal("0"),
            fee_distribution_id=secondary_distribution.distribution_code_id,
            statutory_fees_gst=Decimal("0"),
            service_fees_gst=Decimal("0"),
            description="Secondary Filing Fee",
        ),
        PaymentLineItemModel(
            total=Decimal("0"),
            service_fees=Decimal("0"),
            fee_distribution_id=combined_gst_distribution.distribution_code_id,
            statutory_fees_gst=Decimal("2.50"),
            service_fees_gst=Decimal("1.25"),
            description="Combined GST Test",
        ),
    ]

    lines = cfs_service.build_lines(payment_line_items)

    assert len(lines) == 6

    base_line = next(line for line in lines if "Base Filing Fee" in line["description"])
    service_line = next(line for line in lines if "Service Fee" in line["description"])
    secondary_line = next(line for line in lines if "Secondary Filing Fee" in line["description"])
    statutory_gst_line = next(line for line in lines if "Statutory Fees GST" in line["description"])
    service_gst_line = next(line for line in lines if "Service Fees GST" in line["description"])
    combined_gst_line = next(line for line in lines if "Statutory & Service Fees GST" in line["description"])

    _verify_line_structure(base_line, Decimal("100.00"))
    _verify_line_structure(service_line, Decimal("10.00"))
    _verify_line_structure(secondary_line, Decimal("200.00"))
    _verify_line_structure(statutory_gst_line, Decimal("5.00"))
    _verify_line_structure(service_gst_line, Decimal("0.50"))
    _verify_line_structure(combined_gst_line, Decimal("3.75"))  # 2.50 + 1.25 from combined GST test
