# Copyright © 2019 Province of British Columbia
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
"""Base class for CGI AP."""

import os
from datetime import UTC, datetime

from flask import current_app

from pay_api.models.eft_refund import EFTRefund
from pay_api.utils.enums import DisbursementMethod
from pay_api.utils.util import get_fiscal_year, get_nearest_business_day
from tasks.common.dataclasses import APFlow, APHeader, APLine, APSupplier

from .cgi_ejv import CgiEjv


class CgiAP(CgiEjv):
    """Base class for CGI AP, for routing slip refunds and disbursements to non-government entities."""

    @classmethod
    def get_batch_header(cls, batch_number, batch_type: str = "AP"):
        """Return batch header string."""
        return (
            f"{cls._feeder_number()}{batch_type}BH{cls.DELIMITER}{cls._feeder_number()}"
            f"{get_fiscal_year(datetime.now(tz=UTC))}"
            f"{batch_number}{cls._message_version()}{cls.DELIMITER}{os.linesep}"
        )

    @classmethod
    def get_batch_trailer(cls, batch_number, batch_total, batch_type: str = "AP", control_total: int = 0):
        """Return batch trailer string."""
        return (
            f"{cls._feeder_number()}{batch_type}BT{cls.DELIMITER}{cls._feeder_number()}"
            f"{get_fiscal_year(datetime.now(tz=UTC))}{batch_number}"
            f"{control_total:0>15}{cls.format_amount(batch_total)}{cls.DELIMITER}{os.linesep}"
        )

    @classmethod
    def get_ap_header(cls, ap_header: APHeader):
        """Get AP Invoice Header string."""
        invoice_type = "ST"
        remit_code = f"{current_app.config.get('CGI_AP_REMITTANCE_CODE'):<4}"
        currency = "CAD"
        effective_date = cls._get_date(get_nearest_business_day(datetime.now(tz=UTC)))
        invoice_date = cls._get_date(ap_header.invoice_date)
        oracle_invoice_batch_name = cls._get_oracle_invoice_batch_name(ap_header.ap_flow, ap_header.invoice_number)
        ap_flow_to_disbursement_method = {
            APFlow.NON_GOV_TO_EFT: DisbursementMethod.EFT.value,
            APFlow.EFT_TO_CHEQUE: DisbursementMethod.CHEQUE.value,
            APFlow.ROUTING_SLIP_TO_CHEQUE: DisbursementMethod.CHEQUE.value,
            APFlow.EFT_TO_EFT: DisbursementMethod.EFT.value,
        }
        term = f"Immediate{cls.EMPTY:<41}"

        ap_header = (
            f"{cls._feeder_number()}APIH{cls.DELIMITER}"
            f"{cls._supplier_number(ap_header.ap_flow, ap_header.ap_supplier.supplier_number)}"
            f"{cls._supplier_location(ap_header.ap_flow, ap_header.ap_supplier.supplier_site)}"
            f"{ap_header.invoice_number:<50}{cls._po_number()}{invoice_type}{invoice_date}"
            f"GEN {ap_flow_to_disbursement_method[ap_header.ap_flow]} N{remit_code}{cls.format_amount(ap_header.total)}"
            f"{currency}{effective_date}"
            f"{term}{cls.EMPTY:<60}{cls.EMPTY:<8}{cls.EMPTY:<8}"
            f"{oracle_invoice_batch_name:<30}{cls.EMPTY:<9}Y{cls.EMPTY:<110}{cls.DELIMITER}{os.linesep}"
        )
        return ap_header

    @classmethod
    def get_ap_invoice_line(cls, ap_line: APLine):
        """Get AP Invoice Line string."""
        commit_line_number = f"{cls.EMPTY:<4}"
        # Pad Zeros to four digits. EG. 0001
        line_number = f"{ap_line.line_number:04}"
        effective_date = cls._get_date(get_nearest_business_day(datetime.now(tz=UTC)))
        line_code = cls._get_line_code(ap_line)
        supplier_number = cls._supplier_number(ap_line.ap_flow, ap_line.ap_supplier.supplier_number)
        dist_vendor = cls._dist_vendor(ap_line.ap_flow, ap_line.ap_supplier.supplier_number)
        ap_line = (
            f"{cls._feeder_number()}APIL{cls.DELIMITER}{supplier_number}"
            f"{cls._supplier_location(ap_line.ap_flow, ap_line.ap_supplier.supplier_site)}{ap_line.invoice_number:<50}"
            f"{line_number}{commit_line_number}"
            f"{cls.format_amount(ap_line.total)}{line_code}{cls._distribution(ap_line.ap_flow, ap_line.distribution)}"
            f"{cls.EMPTY:<55}{effective_date}{cls.EMPTY:<10}{cls.EMPTY:<15}{cls.EMPTY:<15}{cls.EMPTY:<15}"
            f"{cls.EMPTY:<15}{cls.EMPTY:<20}{cls.EMPTY:<4}{cls.EMPTY:<30}{cls.EMPTY:<25}{cls.EMPTY:<30}{cls.EMPTY:<8}"
            f"{cls.EMPTY:<1}{dist_vendor}{cls.EMPTY:<110}{cls.DELIMITER}{os.linesep}"
        )
        return ap_line

    @classmethod
    def grab_refund_details(cls, refund_details: dict | EFTRefund):
        """Grab data from dicts or EFTRefund objects."""
        if isinstance(refund_details, EFTRefund):
            name = refund_details.entity_name
            city = refund_details.city
            region = refund_details.region
            postal_code = refund_details.postal_code
            country = refund_details.country
            street = refund_details.street
            street_additional = refund_details.street_additional or f"{cls.EMPTY:<40}"
        else:
            name = refund_details["name"]
            city = refund_details["mailingAddress"]["city"]
            region = refund_details["mailingAddress"]["region"]
            postal_code = refund_details["mailingAddress"]["postalCode"]
            country = refund_details["mailingAddress"]["country"]
            street = refund_details["mailingAddress"]["street"]
            street_additional = (
                refund_details["mailingAddress"]["streetAdditional"]
                if "streetAdditional" in refund_details["mailingAddress"]
                else f"{cls.EMPTY:<40}"
            )
        return name, city, region, postal_code, country, street, street_additional

    @classmethod
    def get_ap_address(cls, ap_flow, refund_details: dict | EFTRefund, ap_invoice_number):
        """Get AP Address Override."""
        name, city, region, postal_code, country, street, street_additional = cls.grab_refund_details(refund_details)
        city = f"{city[:25]:<25}"
        region = f"{region[:2]:<2}"
        postal_code = f"{postal_code[:10].replace(' ', ''):<10}"
        country = f"{country[:2]:<2}"
        street_additional = f"{street_additional[:40]:<40}"
        address_1 = f"{street[:40]:<40}"
        address_2, address_3 = None, None
        if len(street) > 80:
            address_3 = f"{street[80:120]:<40}"
        elif len(street) > 40:
            address_2 = f"{street[40:80]:<40}"
            address_3 = street_additional
        else:
            address_2 = street_additional
            address_3 = f"{cls.EMPTY:<40}"
        ap_address = (
            f"{cls._feeder_number()}APNA{cls.DELIMITER}{cls._supplier_number(ap_flow)}{cls._supplier_location(ap_flow)}"
            f"{ap_invoice_number:<50}{f'{name[:40]:<40}'}{f'{name[40:80]:<40}'}{address_1}{address_2}{address_3}"
            f"{city}{region}{postal_code}{country}{cls.DELIMITER}{os.linesep}"
        )
        return ap_address

    @classmethod
    def get_eft_ap_comment(cls, ap_flow: APFlow, refund: EFTRefund, supplier_line: APSupplier = None):
        """Get AP Comment Override. Combine payment advice on the first line, details on the second."""
        comment = f"{cls.EMPTY:<1}{refund.short_name_id}{cls.EMPTY:<1}-{cls.EMPTY:<1}{refund.comment}"[:40]
        line_text = "0001"
        ap_comment_line = (
            f"{cls._feeder_number()}APIC{cls.DELIMITER}{cls._supplier_number(ap_flow, supplier_line.supplier_number)}"
            f"{cls._supplier_location(ap_flow, supplier_line.supplier_site)}{refund.id:<50}{line_text}{comment}"
            f"{cls.DELIMITER}{os.linesep}"
        )
        return ap_comment_line

    @classmethod
    def get_rs_ap_comment(cls, refund_details, rs_number):
        """Get AP Comment Override. Routing slip only."""
        if not (cheque_advice := refund_details.get("chequeAdvice", "")):
            return None
        cheque_advice = cheque_advice[:40]
        line_text = "0001"
        ap_comment = (
            f"{cls._feeder_number()}APIC{cls.DELIMITER}{cls._supplier_number(APFlow.ROUTING_SLIP_TO_CHEQUE)}"
            f"{cls._supplier_location(APFlow.ROUTING_SLIP_TO_CHEQUE)}{rs_number:<50}{line_text}{cheque_advice}"
            f"{cls.DELIMITER}{os.linesep}"
        )
        return ap_comment

    @classmethod
    def _supplier_number(cls, ap_flow: APFlow = None, supplier_number: str = None):
        """Return vendor number."""
        match ap_flow:
            case APFlow.NON_GOV_TO_EFT:
                return f"{current_app.config.get('BCA_SUPPLIER_NUMBER'):<9}"
            case APFlow.ROUTING_SLIP_TO_CHEQUE | APFlow.EFT_TO_CHEQUE:
                return f"{current_app.config.get('CGI_AP_SUPPLIER_NUMBER'):<9}"
            case APFlow.EFT_TO_EFT:
                return f"{supplier_number:<9}"
            case _:
                raise RuntimeError("ap_flow not selected.")

    @classmethod
    def _dist_vendor(cls, ap_flow: APFlow, supplier_number: str = None):
        """Return distribution vendor number."""
        match ap_flow:
            case APFlow.NON_GOV_TO_EFT:
                return f"{current_app.config.get('BCA_SUPPLIER_NUMBER'):<30}"
            case APFlow.ROUTING_SLIP_TO_CHEQUE | APFlow.EFT_TO_CHEQUE:
                return f"{current_app.config.get('CGI_AP_SUPPLIER_NUMBER'):<30}"
            case APFlow.EFT_TO_EFT:
                return f"{supplier_number:<30}"
            case _:
                raise RuntimeError("ap_flow not selected.")

    @classmethod
    def _supplier_location(cls, ap_flow: APFlow, supplier_site: str = None):
        """Return location."""
        match ap_flow:
            case APFlow.NON_GOV_TO_EFT:
                return f"{current_app.config.get('BCA_SUPPLIER_LOCATION'):<3}"
            case APFlow.ROUTING_SLIP_TO_CHEQUE | APFlow.EFT_TO_CHEQUE:
                return f"{current_app.config.get('CGI_AP_SUPPLIER_LOCATION'):<3}"
            case APFlow.EFT_TO_EFT:
                return f"{supplier_site:<3}"
            case _:
                raise RuntimeError("ap_flow not selected.")

    @classmethod
    def _po_number(cls):
        """Return PO Number."""
        return f"{cls.EMPTY:<20}"

    @classmethod
    def _get_date(cls, date):
        """Return date."""
        return date.strftime("%Y%m%d")

    @classmethod
    def _distribution(cls, ap_flow: APFlow, distribution_code: str = None):
        """Return Distribution Code string."""
        match ap_flow:
            case APFlow.NON_GOV_TO_EFT:
                return f"{distribution_code}0000000000{cls.EMPTY:<16}"
            case APFlow.ROUTING_SLIP_TO_CHEQUE:
                return f"{current_app.config.get('CGI_AP_DISTRIBUTION')}{cls.EMPTY:<16}"
            case APFlow.EFT_TO_CHEQUE | APFlow.EFT_TO_EFT:
                return f"{current_app.config.get('EFT_AP_DISTRIBUTION')}{cls.EMPTY:<16}"
            case _:
                raise RuntimeError("ap_flow not selected.")

    @classmethod
    def _get_oracle_invoice_batch_name(cls, ap_flow, invoice_number):
        """Return Oracle Invoice Batch Name."""
        match ap_flow:
            case APFlow.NON_GOV_TO_EFT:
                return f"{invoice_number}"[:30]
            case APFlow.ROUTING_SLIP_TO_CHEQUE:
                return f"REFUND_FAS_RS_{invoice_number}"[:30]
            case APFlow.EFT_TO_EFT | APFlow.EFT_TO_CHEQUE:
                return f"REFUND_EFT_{invoice_number}"[:30]
            case _:
                raise RuntimeError("ap_flow not selected.")

    @classmethod
    def _get_line_code(cls, ap_line: APLine):
        """Get line code."""
        match ap_line.ap_flow:
            case APFlow.EFT_TO_EFT | APFlow.EFT_TO_CHEQUE | APFlow.ROUTING_SLIP_TO_CHEQUE:
                return "D"
            case APFlow.NON_GOV_TO_EFT:
                return "C" if ap_line.is_reversal else "D"
            case _:
                raise RuntimeError("ap_flow not selected.")
