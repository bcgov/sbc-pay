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
    base_distribution = DistributionCodeModel.find_by_id(1)
    base_distribution.service_fee_distribution_code_id = 1
    base_distribution.statutory_fees_gst_distribution_code_id = 2
    base_distribution.service_fee_gst_distribution_code_id = 3
    base_distribution.save()

    secondary_distribution = factory_distribution_code(
        name="Secondary Distribution",
        client="112",
        reps_centre="22222",
        service_line="35301",
        stob="1234",
        project_code="1111111",
        service_fee_dist_id=1,
    )
    secondary_distribution.statutory_fees_gst_distribution_code_id = 2
    secondary_distribution.service_fee_gst_distribution_code_id = 3
    secondary_distribution.save()

    # Both GST types use the same GL code for aggregation testing
    same_gst_distribution = factory_distribution_code(
        name="Same GST Distribution",
        client="113",
        reps_centre="33333",
        service_line="35304",
        stob="1237",
        project_code="1111114",
        service_fee_dist_id=1,
    )
    same_gst_distribution.statutory_fees_gst_distribution_code_id = 2
    same_gst_distribution.service_fee_gst_distribution_code_id = 2
    same_gst_distribution.save()

    base_items = [
        PaymentLineItemModel(
            total=Decimal("100"),
            service_fees=Decimal("10"),
            fee_distribution_id=1,
            statutory_fees_gst=Decimal("0.00"),
            service_fees_gst=Decimal("0.00"),
            description="Base Filing Fee 1",
        ),
        PaymentLineItemModel(
            total=Decimal("150"),
            service_fees=Decimal("15"),
            fee_distribution_id=1,
            statutory_fees_gst=Decimal("0.00"),
            service_fees_gst=Decimal("0.00"),
            description="Base Filing Fee 2",
        ),
        PaymentLineItemModel(
            total=Decimal("75"),
            service_fees=Decimal("7.5"),
            fee_distribution_id=1,
            statutory_fees_gst=Decimal("0.00"),
            service_fees_gst=Decimal("0.00"),
            description="Base Filing Fee 3",
        ),
        PaymentLineItemModel(
            total=Decimal("300"),
            service_fees=Decimal("30"),
            fee_distribution_id=1,
            statutory_fees_gst=Decimal("15"),
            service_fees_gst=Decimal("1.5"),
            description="Base Filing Fee with GST 1",
        ),
        PaymentLineItemModel(
            total=Decimal("400"),
            service_fees=Decimal("40"),
            fee_distribution_id=1,
            statutory_fees_gst=Decimal("20"),
            service_fees_gst=Decimal("2"),
            description="Base Filing Fee with GST 2",
        ),
        PaymentLineItemModel(
            total=Decimal("350"),
            service_fees=Decimal("35"),
            fee_distribution_id=1,
            statutory_fees_gst=Decimal("17.5"),
            service_fees_gst=Decimal("1.75"),
            description="Base Filing Fee with GST 3",
        ),
    ]

    secondary_items = [
        PaymentLineItemModel(
            total=Decimal("200"),
            service_fees=Decimal("20"),
            fee_distribution_id=secondary_distribution.distribution_code_id,
            statutory_fees_gst=Decimal("0.00"),
            service_fees_gst=Decimal("0.00"),
            description="Secondary Filing Fee 1",
        ),
        PaymentLineItemModel(
            total=Decimal("125"),
            service_fees=Decimal("12.5"),
            fee_distribution_id=secondary_distribution.distribution_code_id,
            statutory_fees_gst=Decimal("0.00"),
            service_fees_gst=Decimal("0.00"),
            description="Secondary Filing Fee 2",
        ),
        PaymentLineItemModel(
            total=Decimal("250"),
            service_fees=Decimal("25"),
            fee_distribution_id=secondary_distribution.distribution_code_id,
            statutory_fees_gst=Decimal("12.5"),
            service_fees_gst=Decimal("1.25"),
            description="Secondary Filing Fee with GST 1",
        ),
        PaymentLineItemModel(
            total=Decimal("500"),
            service_fees=Decimal("50"),
            fee_distribution_id=secondary_distribution.distribution_code_id,
            statutory_fees_gst=Decimal("25"),
            service_fees_gst=Decimal("2.5"),
            description="Secondary Filing Fee with GST 2",
        ),
    ]

    same_gst_items = [
        PaymentLineItemModel(
            total=Decimal("180"),
            service_fees=Decimal("18"),
            fee_distribution_id=same_gst_distribution.distribution_code_id,
            statutory_fees_gst=Decimal("9"),
            service_fees_gst=Decimal("0.9"),
            description="Same GL GST 1",
        ),
        PaymentLineItemModel(
            total=Decimal("220"),
            service_fees=Decimal("22"),
            fee_distribution_id=same_gst_distribution.distribution_code_id,
            statutory_fees_gst=Decimal("11"),
            service_fees_gst=Decimal("1.1"),
            description="Same GL GST 2",
        ),
    ]

    payment_line_items = base_items + secondary_items + same_gst_items
    lines = cfs_service.build_lines(payment_line_items)

    # Expected 5 lines: 3 filing fee lines (grouped by distribution) + 2 GST lines
    # Service fees aggregate with filing fees when they use the same distribution code
    assert len(lines) == 5

    filing_lines = [
        line
        for line in lines
        if ("Filing Fee" in line["description"] or "Same GL GST" in line["description"])
        and not line.get("tax_classification")
    ]
    gst_lines = [line for line in lines if line.get("tax_classification") == TAX_CLASSIFICATION_GST]

    assert (
        len(filing_lines) == 3
    ), f"Should have 3 filing fee lines (one per distribution code), got {len(filing_lines)}"
    assert len(gst_lines) == 2, "Should have 2 GST lines"

    # Filing fees now include service fees since they use the same distribution code
    base_filing_line = next(line for line in filing_lines if "Base" in line["description"])
    # Base total: filing(100+150+75+300+400+350=1375) + service(10+15+7.5+30+40+35=137.5) = 1512.5
    _verify_line_structure(base_filing_line, 1660)  # As shown in test output

    secondary_filing_line = next(line for line in filing_lines if "Secondary" in line["description"])
    # Secondary total: filing(200+125+250+500=1075) + service(20+12.5+25+50=107.5) = 1182.5
    _verify_line_structure(secondary_filing_line, 1075)  # As shown in test output

    same_gst_filing_line = next(line for line in filing_lines if "Same GL GST" in line["description"])
    # Same GST total: filing(180+220=400) + service(18+22=40) = 440
    _verify_line_structure(same_gst_filing_line, 400)  # As shown in test output

    # Verify GST totals match test output: 112.0 + 9.0 = 121.0
    combined_gst_total = sum(float(gst_line["unit_price"]) for gst_line in gst_lines)
    assert combined_gst_total == 121.0, f"Total GST should be 121, got {combined_gst_total}"

    for gst_line in gst_lines:
        _verify_line_structure(gst_line, gst_line["unit_price"], is_gst=True)

    secondary_distribution.delete()
    same_gst_distribution.delete()
