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
from datetime import datetime, timezone

from flask import current_app
from pay_api.utils.enums import DisbursementMethod, EjvFileType
from pay_api.utils.util import get_fiscal_year

from tasks.common.dataclasses import APLine

from .cgi_ejv import CgiEjv


class CgiAP(CgiEjv):
    """Base class for CGI AP, for routing slip refunds and disbursements to non-government entities."""

    ap_type: EjvFileType

    @classmethod
    def get_batch_header(cls, batch_number, batch_type: str = "AP"):
        """Return batch header string."""
        return (
            f"{cls._feeder_number()}{batch_type}BH{cls.DELIMITER}{cls._feeder_number()}"
            f"{get_fiscal_year(datetime.now(tz=timezone.utc))}"
            f"{batch_number}{cls._message_version()}{cls.DELIMITER}{os.linesep}"
        )

    @classmethod
    def get_batch_trailer(cls, batch_number, batch_total, batch_type: str = "AP", control_total: int = 0):
        """Return batch trailer string."""
        return (
            f"{cls._feeder_number()}{batch_type}BT{cls.DELIMITER}{cls._feeder_number()}"
            f"{get_fiscal_year(datetime.now(tz=timezone.utc))}{batch_number}"
            f"{control_total:0>15}{cls.format_amount(batch_total)}{cls.DELIMITER}{os.linesep}"
        )

    @classmethod
    def get_ap_header(cls, total, invoice_number, invoice_date,   # pylint: disable=too-many-arguments
                      supplier_number: str = None, supplier_site: str = None):
        """Get AP Invoice Header string."""
        invoice_type = "ST"
        remit_code = f"{current_app.config.get('CGI_AP_REMITTANCE_CODE'):<4}"
        currency = "CAD"
        effective_date = cls._get_date(datetime.now(tz=timezone.utc))
        invoice_date = cls._get_date(invoice_date)
        oracle_invoice_batch_name = cls._get_oracle_invoice_batch_name(invoice_number)
        disbursement_method = (
            DisbursementMethod.CHEQUE.value if cls.ap_type == EjvFileType.REFUND else DisbursementMethod.EFT.value
        )
        term = f"{cls.EMPTY:<50}" if cls.ap_type == EjvFileType.REFUND else f"Immediate{cls.EMPTY:<41}"
        ap_header = (
            f"{cls._feeder_number()}APIH{cls.DELIMITER}{cls._supplier_number(supplier_number)}"
            f"{cls._supplier_location(supplier_site)}{invoice_number:<50}{cls._po_number()}{invoice_type}{invoice_date}"
            f"GEN {disbursement_method} N{remit_code}{cls.format_amount(total)}{currency}{effective_date}"
            f"{term}{cls.EMPTY:<60}{cls.EMPTY:<8}{cls.EMPTY:<8}"
            f"{oracle_invoice_batch_name:<30}{cls.EMPTY:<9}Y{cls.EMPTY:<110}{cls.DELIMITER}{os.linesep}"
        )
        return ap_header

    @classmethod
    def get_ap_invoice_line(cls, ap_line: APLine, supplier_number: str = None, supplier_site: str = None):
        """Get AP Invoice Line string."""
        commit_line_number = f"{cls.EMPTY:<4}"
        # Pad Zeros to four digits. EG. 0001
        line_number = f"{ap_line.line_number:04}"
        effective_date = cls._get_date(datetime.now(tz=timezone.utc))
        line_code = cls._get_line_code(ap_line)
        ap_line = (
            f"{cls._feeder_number()}APIL{cls.DELIMITER}{cls._supplier_number(supplier_number)}"
            f"{cls._supplier_location(supplier_site)}{ap_line.invoice_number:<50}{line_number}{commit_line_number}"
            f"{cls.format_amount(ap_line.total)}{line_code}{cls._distribution(ap_line.distribution)}{cls.EMPTY:<55}"
            f"{effective_date}{cls.EMPTY:<10}{cls.EMPTY:<15}{cls.EMPTY:<15}{cls.EMPTY:<15}{cls.EMPTY:<15}"
            f"{cls.EMPTY:<20}{cls.EMPTY:<4}{cls.EMPTY:<30}{cls.EMPTY:<25}{cls.EMPTY:<30}{cls.EMPTY:<8}{cls.EMPTY:<1}"
            f"{cls._dist_vendor(supplier_number)}{cls.EMPTY:<110}{cls.DELIMITER}{os.linesep}"
        )
        return ap_line

    @classmethod
    def get_ap_address(cls, refund_details, routing_slip_number):
        """Get AP Address Override. Routing Slip only."""
        name_1 = f"{refund_details['name'][:40]:<40}"
        name_2 = f"{refund_details['name'][40:80]:<40}"

        street = refund_details["mailingAddress"]["street"]
        street_additional = (
            f"{refund_details['mailingAddress']['streetAdditional'][:40]:<40}"
            if "streetAdditional" in refund_details["mailingAddress"]
            else f"{cls.EMPTY:<40}"
        )
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

        city = f"{refund_details['mailingAddress']['city'][:25]:<25}"
        prov = f"{refund_details['mailingAddress']['region'][:2]:<2}"
        postal_code = f"{refund_details['mailingAddress']['postalCode'][:10].replace(' ', ''):<10}"
        country = f"{refund_details['mailingAddress']['country'][:2]:<2}"

        ap_address = (
            f"{cls._feeder_number()}APNA{cls.DELIMITER}{cls._supplier_number()}{cls._supplier_location()}"
            f"{routing_slip_number:<50}{name_1}{name_2}{address_1}{address_2}{address_3}"
            f"{city}{prov}{postal_code}{country}{cls.DELIMITER}{os.linesep}"
        )
        return ap_address

    @classmethod
    def get_eft_ap_comment(cls, comment, refund_id, short_name_id,   # pylint: disable=too-many-arguments
                           supplier_number, supplier_site):
        """Get AP Comment Override. EFT only."""
        line_text = "0001"
        combined_comment = f"{cls.EMPTY:<1}{short_name_id}{cls.EMPTY:<1}-{cls.EMPTY:<1}{comment}"[:40]
        ap_comment = (
            f"{cls._feeder_number()}APIC{cls.DELIMITER}{cls._supplier_number(supplier_number)}"
            f"{cls._supplier_location(supplier_site)}{refund_id:<50}{line_text}{combined_comment}"
            f"{cls.DELIMITER}{os.linesep}"
        )
        return ap_comment

    @classmethod
    def get_rs_ap_comment(cls, refund_details, routing_slip_number):
        """Get AP Comment Override. Routing slip only."""
        if not (cheque_advice := refund_details.get("chequeAdvice", "")):
            return None
        cheque_advice = cheque_advice[:40]
        line_text = "0001"
        ap_comment = (
            f"{cls._feeder_number()}APIC{cls.DELIMITER}{cls._supplier_number()}"
            f"{cls._supplier_location()}{routing_slip_number:<50}{line_text}{cheque_advice}"
            f"{cls.DELIMITER}{os.linesep}"
        )
        return ap_comment

    @classmethod
    def _supplier_number(cls, supplier_number: str = None):
        """Return vendor number."""
        if supplier_number:
            return f"{supplier_number:<9}"
        match cls.ap_type:
            case EjvFileType.NON_GOV_DISBURSEMENT:
                return f"{current_app.config.get('BCA_SUPPLIER_NUMBER'):<9}"
            case EjvFileType.REFUND:
                return f"{current_app.config.get('CGI_AP_SUPPLIER_NUMBER'):<9}"
            case _:
                raise RuntimeError("ap_type not selected.")

    @classmethod
    def _dist_vendor(cls, supplier_number: str = None):
        """Return distribution vendor number."""
        if supplier_number:
            return f"{supplier_number:<30}"
        match cls.ap_type:
            case EjvFileType.NON_GOV_DISBURSEMENT:
                return f"{current_app.config.get('BCA_SUPPLIER_NUMBER'):<30}"
            case EjvFileType.REFUND:
                return f"{current_app.config.get('CGI_AP_SUPPLIER_NUMBER'):<30}"
            case _:
                raise RuntimeError("ap_type not selected.")

    @classmethod
    def _supplier_location(cls, supplier_site: str = None):
        """Return location."""
        if supplier_site:
            return f"{supplier_site:<3}"
        match cls.ap_type:
            case EjvFileType.NON_GOV_DISBURSEMENT:
                return f"{current_app.config.get('BCA_SUPPLIER_LOCATION'):<3}"
            case EjvFileType.REFUND:
                return f"{current_app.config.get('CGI_AP_SUPPLIER_LOCATION'):<3}"
            case EjvFileType.EFT_REFUND:
                return f"{current_app.config.get('EFT_AP_SUPPLIER_LOCATION'):<3}"
            case _:
                raise RuntimeError("ap_type not selected.")

    @classmethod
    def _po_number(cls):
        """Return PO Number."""
        return f"{cls.EMPTY:<20}"

    @classmethod
    def _get_date(cls, date):
        """Return date."""
        return date.strftime("%Y%m%d")

    @classmethod
    def _distribution(cls, distribution_code: str = None):
        """Return Distribution Code string."""
        match cls.ap_type:
            case EjvFileType.NON_GOV_DISBURSEMENT:
                return f"{distribution_code}0000000000{cls.EMPTY:<16}"
            case EjvFileType.REFUND:
                return f"{current_app.config.get('CGI_AP_DISTRIBUTION')}{cls.EMPTY:<16}"
            case EjvFileType.EFT_REFUND:
                return f"{current_app.config.get('EFT_AP_DISTRIBUTION')}{cls.EMPTY:<16}"
            case _:
                raise RuntimeError("ap_type not selected.")

    @classmethod
    def _get_oracle_invoice_batch_name(cls, invoice_number):
        """Return Oracle Invoice Batch Name."""
        match cls.ap_type:
            case EjvFileType.NON_GOV_DISBURSEMENT:
                return f"{invoice_number}"[:30]
            case EjvFileType.REFUND:
                return f"REFUND_FAS_RS_{invoice_number}"[:30]
            case EjvFileType.EFT_REFUND:
                return f"REFUND_EFT_{invoice_number}"[:30]
            case _:
                raise RuntimeError("ap_type not selected.")

    @classmethod
    def _get_line_code(cls, ap_line: APLine):
        """Get line code."""
        match cls.ap_type:
            case EjvFileType.REFUND | EjvFileType.EFT_REFUND:
                return "D"
            case EjvFileType.NON_GOV_DISBURSEMENT:
                return "C" if ap_line.is_reversal else "D"
            case _:
                raise RuntimeError("ap_type not selected.")
