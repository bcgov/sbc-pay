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

cfs_service = CFSService()


def test_validate_bank_account_valid(session):
    """Test create_account."""
    input_bank_details = {
        "bankInstitutionNumber": "2001",
        "bankTransitNumber": "00720",
        "bankAccountNumber": "1234567",
    }
    with patch("pay_api.services.oauth_service.requests.post") as mock_post:
        # Configure the mock to return a response with an OK status code.
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
        # Configure the mock to return a response with an OK status code.
        bank_details = cfs_service.validate_bank_account(input_bank_details)
        assert bank_details.get("status_code") == 503
        assert "mocked error" in bank_details.get("message")


def test_ensure_totals_quantized(session):
    """Test payment line items that usually add up to bad float math."""
    # print(0.3+0.55+0.55)
    # results in 1.4000000000000001
    # print(float(Decimal('0.3')+Decimal('0.55')+Decimal('0.55')))
    # results in 1.4

    distribution_code = DistributionCodeModel.find_by_id(1)
    distribution_code.service_fee_distribution_code_id = 1
    distribution_code.save()

    payment_line_items = [
        PaymentLineItemModel(total=Decimal("0.3"), service_fees=Decimal("0.3"), fee_distribution_id=1),
        PaymentLineItemModel(total=Decimal("0.55"), service_fees=Decimal("0.55"), fee_distribution_id=1),
        PaymentLineItemModel(
            total=Decimal("0.55"),
            service_fees=Decimal("0.55"),
            fee_distribution_id=1,
        ),
    ]
    lines = cfs_service.build_lines(payment_line_items)  # pylint: disable=protected-access
    # Same distribution code for filing fees and service fees.
    assert float(lines[0]["unit_price"]) == 2.8


def test_build_lines_with_gst_fees(session):
    """Test build_lines with statutory and service fees GST."""
    base_distribution = DistributionCodeModel.find_by_id(1)
    base_distribution.service_fee_distribution_code_id = 1
    base_distribution.statutory_fees_gst_distribution_code_id = 2
    base_distribution.service_fee_gst_distribution_code_id = 3
    base_distribution.save()

    secondary_distribution = DistributionCodeModel(
        name="Secondary Distribution",
        client="112",
        responsibility_centre="22222",
        service_line="35301",
        stob="1234",
        project_code="1111111",
        service_fee_distribution_code_id=1,
        statutory_fees_gst_distribution_code_id=2,
        service_fee_gst_distribution_code_id=3,
    )
    secondary_distribution.save()

    # Distribution code where both GST types use the same GL code
    same_gst_distribution = DistributionCodeModel(
        name="Same GST Distribution",
        client="113",
        responsibility_centre="33333",
        service_line="35304",
        stob="1237",
        project_code="1111114",
        service_fee_distribution_code_id=1,
        statutory_fees_gst_distribution_code_id=2,  # Same as service_fee_gst
        service_fee_gst_distribution_code_id=2,  # Same as statutory_fees_gst
    )
    same_gst_distribution.save()

    gst_statutory_distribution = DistributionCodeModel(
        name="GST Statutory Distribution",
        client="112",
        responsibility_centre="22222",
        service_line="35302",
        stob="1235",
        project_code="1111112",
    )
    gst_statutory_distribution.save()

    gst_service_distribution = DistributionCodeModel(
        name="GST Service Distribution",
        client="112",
        responsibility_centre="22222",
        service_line="35303",
        stob="1236",
        project_code="1111113",
    )
    gst_service_distribution.save()

    # Create 12 payment line items: 5 without GST, 5 with separate GST, 2 with same GL GST
    payment_line_items = [
        # Items without GST
        PaymentLineItemModel(
            total=Decimal("100.00"), service_fees=Decimal("10.00"), fee_distribution_id=1, description="Filing Fee 1"
        ),
        PaymentLineItemModel(
            total=Decimal("150.00"), service_fees=Decimal("15.00"), fee_distribution_id=1, description="Filing Fee 2"
        ),
        PaymentLineItemModel(
            total=Decimal("200.00"),
            service_fees=Decimal("20.00"),
            fee_distribution_id=secondary_distribution.distribution_code_id,
            description="Filing Fee 3",
        ),
        PaymentLineItemModel(
            total=Decimal("75.00"), service_fees=Decimal("7.50"), fee_distribution_id=1, description="Filing Fee 4"
        ),
        PaymentLineItemModel(
            total=Decimal("125.00"),
            service_fees=Decimal("12.50"),
            fee_distribution_id=secondary_distribution.distribution_code_id,
            description="Filing Fee 5",
        ),
        # Items with both statutory_fees_gst and service_fees_gst
        PaymentLineItemModel(
            total=Decimal("300.00"),
            service_fees=Decimal("30.00"),
            statutory_fees_gst=Decimal("15.00"),
            service_fees_gst=Decimal("1.50"),
            fee_distribution_id=1,
            description="Filing Fee with GST 1",
        ),
        PaymentLineItemModel(
            total=Decimal("400.00"),
            service_fees=Decimal("40.00"),
            statutory_fees_gst=Decimal("20.00"),
            service_fees_gst=Decimal("2.00"),
            fee_distribution_id=1,
            description="Filing Fee with GST 2",
        ),
        PaymentLineItemModel(
            total=Decimal("250.00"),
            service_fees=Decimal("25.00"),
            statutory_fees_gst=Decimal("12.50"),
            service_fees_gst=Decimal("1.25"),
            fee_distribution_id=secondary_distribution.distribution_code_id,
            description="Filing Fee with GST 3",
        ),
        PaymentLineItemModel(
            total=Decimal("350.00"),
            service_fees=Decimal("35.00"),
            statutory_fees_gst=Decimal("17.50"),
            service_fees_gst=Decimal("1.75"),
            fee_distribution_id=1,
            description="Filing Fee with GST 4",
        ),
        PaymentLineItemModel(
            total=Decimal("500.00"),
            service_fees=Decimal("50.00"),
            statutory_fees_gst=Decimal("25.00"),
            service_fees_gst=Decimal("2.50"),
            fee_distribution_id=secondary_distribution.distribution_code_id,
            description="Filing Fee with GST 5",
        ),
        # Items where both GST types use the same GL code (should be aggregated)
        PaymentLineItemModel(
            total=Decimal("180.00"),
            service_fees=Decimal("18.00"),
            statutory_fees_gst=Decimal("9.00"),  # Will aggregate with service_fees_gst
            service_fees_gst=Decimal("0.90"),  # Will aggregate with statutory_fees_gst
            fee_distribution_id=same_gst_distribution.distribution_code_id,
            description="Same GL GST 1",
        ),
        PaymentLineItemModel(
            total=Decimal("220.00"),
            service_fees=Decimal("22.00"),
            statutory_fees_gst=Decimal("11.00"),  # Will aggregate with service_fees_gst
            service_fees_gst=Decimal("1.10"),  # Will aggregate with statutory_fees_gst
            fee_distribution_id=same_gst_distribution.distribution_code_id,
            description="Same GL GST 2",
        ),
    ]

    lines = cfs_service.build_lines(payment_line_items)

    # Should have 4 line types: filing fees, service fees, and 2 GST lines (one combined, one separate)
    assert len(lines) == 4

    filing_line = next(line for line in lines if "Filing Fee" in line["description"])
    service_line = next(line for line in lines if line["description"] == "Service Fee")
    
    gst_lines = [line for line in lines if line.get("tax_classification") == "gst"]
    assert len(gst_lines) == 2
    
    combined_gst_line = next((line for line in gst_lines if line["description"] == "Statutory & Service Fees GST"), None)
    separate_gst_line = next((line for line in gst_lines if line["description"] != "Statutory & Service Fees GST"), None)
    
    assert combined_gst_line is not None, "Should have a combined GST line"
    assert separate_gst_line is not None, "Should have a separate GST line"

    # Verify filing fees total: all 12 line items should be aggregated
    expected_filing_total = float(
        Decimal("100")
        + Decimal("150")
        + Decimal("75")
        + Decimal("300")
        + Decimal("400")
        + Decimal("350")
        + Decimal("200")
        + Decimal("125")
        + Decimal("250")
        + Decimal("500")
        + Decimal("180")
        + Decimal("220")
    )
    assert float(filing_line["unit_price"]) == expected_filing_total

    # Verify service fees total: all 12 line items should be aggregated
    expected_service_total = float(
        Decimal("10")
        + Decimal("15")
        + Decimal("7.50")
        + Decimal("30")
        + Decimal("40")
        + Decimal("35")
        + Decimal("20")
        + Decimal("12.50")
        + Decimal("25")
        + Decimal("50")
        + Decimal("18")
        + Decimal("22")
    )
    assert float(service_line["unit_price"]) == expected_service_total

    # Verify combined GST total: aggregated GST from 2 same-GL items
    # Same GL items (both statutory and service GST): (9+0.9) + (11+1.1) = 22
    expected_combined_gst = float(
        Decimal("9.00")
        + Decimal("0.90")
        + Decimal("11.00")
        + Decimal("1.10")
    )
    assert float(combined_gst_line["unit_price"]) == expected_combined_gst
    assert combined_gst_line["tax_classification"] == "gst"

    # Verify separate GST total: original 5 items with different GL codes
    # Statutory: 15+20+12.5+17.5+25 = 90
    # Service: 1.5+2+1.25+1.75+2.5 = 9
    # Total: 90 + 9 = 99
    expected_separate_gst = float(
        Decimal("15")
        + Decimal("20")
        + Decimal("12.50")
        + Decimal("17.50")
        + Decimal("25")
        + Decimal("1.50")
        + Decimal("2.00")
        + Decimal("1.25")
        + Decimal("1.75")
        + Decimal("2.50")
    )
    assert float(separate_gst_line["unit_price"]) == expected_separate_gst
    assert separate_gst_line["tax_classification"] == "gst"

    assert combined_gst_line["line_type"] == "LINE"
    assert separate_gst_line["line_type"] == "LINE"

    for line in lines:
        if line.get("distribution"):
            account = line["distribution"][0]["account"]
            assert len(account.split(".")) == 7
            assert account.endswith(".000000.0000")

    secondary_distribution.delete()
    same_gst_distribution.delete()
    gst_statutory_distribution.delete()
    gst_service_distribution.delete()
