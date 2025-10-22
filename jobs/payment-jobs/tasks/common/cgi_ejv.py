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
"""Base class for CGI EJV."""

import os
import tempfile
from datetime import UTC, datetime

from flask import current_app

from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.services.google_bucket_service import GoogleBucketService
from pay_api.utils.util import get_fiscal_year, get_nearest_business_day


class CgiEjv:
    """Base class for CGI EJV."""

    DELIMITER = chr(29)  # '<0x1d>'
    EMPTY = ""

    @classmethod
    def get_file_name(cls):
        """Return file name."""
        date_time = get_nearest_business_day(datetime.now(tz=UTC)).strftime("%Y%m%d%H%M%S")
        return f"INBOX.F{cls._feeder_number()}.{date_time}"

    @classmethod
    def get_journal_batch_name(cls, batch_number: str):
        """Return journal batch name."""
        return f"{cls.ministry()}{batch_number}{cls.EMPTY:<14}"

    @classmethod
    def _feeder_number(cls):
        """Return feeder number."""
        return current_app.config.get("CGI_FEEDER_NUMBER")

    @classmethod
    def ministry(cls):
        """Return ministry prefix."""
        return current_app.config.get("CGI_MINISTRY_PREFIX")

    @classmethod
    def _message_version(cls):
        """Return message version."""
        return current_app.config.get("CGI_MESSAGE_VERSION")

    @classmethod
    def _supplier_number(cls):
        """Return supplier number (Vendor) - from 6.2.1.3 on the spec."""
        return f"{current_app.config.get('CGI_EJV_SUPPLIER_NUMBER'):<9}"

    @classmethod
    def get_jv_line(  # pylint:disable=too-many-arguments
        cls,
        batch_type,
        distribution,
        description,
        effective_date,
        flow_through,
        journal_name,
        amount,
        line_number,
        credit_debit,
    ):
        """Return jv line string."""
        return (
            f"{cls._feeder_number()}{batch_type}JD{cls.DELIMITER}{journal_name}"
            f"{line_number:0>5}{effective_date}{distribution}{cls._supplier_number()}"
            f"{cls.format_amount(amount)}{credit_debit}{description}{flow_through}"
            f"{cls.DELIMITER}{os.linesep}"
        )

    @classmethod
    def get_batch_header(cls, batch_number, batch_type):
        """Return batch header string."""
        return (
            f"{cls._feeder_number()}{batch_type}BH{cls.DELIMITER}{cls._feeder_number()}"
            f"{get_fiscal_year(datetime.now(tz=UTC))}"
            f"{batch_number}{cls._message_version()}{cls.DELIMITER}{os.linesep}"
        )

    @classmethod
    def get_effective_date(cls):
        """Return effective date.."""
        return get_nearest_business_day(datetime.now(tz=UTC)).strftime("%Y%m%d")

    @classmethod
    def format_amount(cls, amount: float):
        """Format and return amount to fix 2 decimal places and total of length 15 prefixed with zeroes."""
        formatted_amount: str = f"{amount:.2f}"
        return formatted_amount.zfill(15)

    @classmethod
    def get_distribution_string(cls, dist_code: DistributionCodeModel):
        """Return GL code combination for the distribution."""
        return (
            f"{dist_code.client}{dist_code.responsibility_centre}{dist_code.service_line}"
            f"{dist_code.stob}{dist_code.project_code}0000000000{cls.EMPTY:<16}"
        )

    @classmethod
    def upload(cls, file_path_with_name, trg_file_path):
        """Upload to Google bucket."""
        google_storage_client = GoogleBucketService.get_client()
        bucket_name = current_app.config.get("GOOGLE_BUCKET_NAME")
        bucket = GoogleBucketService.get_bucket(google_storage_client, bucket_name)
        bucket_folder_name = current_app.config.get("GOOGLE_BUCKET_FOLDER_CGI_PROCESSING")
        GoogleBucketService.upload_to_bucket_folder(bucket, bucket_folder_name, file_path_with_name)
        GoogleBucketService.upload_to_bucket_folder(bucket, bucket_folder_name, trg_file_path)

    @classmethod
    def get_jv_header(cls, batch_type, journal_batch_name, journal_name, total):
        """Get JV Header string."""
        ejv_content = (
            f"{cls._feeder_number()}{batch_type}JH{cls.DELIMITER}{journal_name}"
            f"{journal_batch_name}{cls.format_amount(total)}ACAD{cls.EMPTY:<100}{cls.EMPTY:<110}"
            f"{cls.DELIMITER}{os.linesep}"
        )
        return ejv_content

    @classmethod
    def get_batch_trailer(cls, batch_number, batch_total, batch_type, control_total):
        """Return batch trailer string."""
        return (
            f"{cls._feeder_number()}{batch_type}BT{cls.DELIMITER}{cls._feeder_number()}"
            f"{get_fiscal_year(datetime.now(tz=UTC))}{batch_number}"
            f"{control_total:0>15}{cls.format_amount(batch_total)}{cls.DELIMITER}{os.linesep}"
        )

    @classmethod
    def get_journal_name(cls, ejv_header_id: int):
        """Return journal name."""
        return f"{cls.ministry()}{ejv_header_id:0>8}"

    @classmethod
    def get_batch_number(cls, ejv_file_id: int) -> str:
        """Return batch number."""
        return f"{ejv_file_id:0>9}"

    @classmethod
    def get_trg_suffix(cls):
        """Return trigger file suffix."""
        return current_app.config.get("CGI_TRIGGER_FILE_SUFFIX")

    @classmethod
    def create_inbox_and_trg_files(cls, ejv_content, file_name):
        """Create inbox and trigger files."""
        file_path: str = tempfile.gettempdir()
        file_path_with_name = f"{file_path}/{file_name}"
        trg_file_path = f"{file_path_with_name}.{cls.get_trg_suffix()}"
        with open(file_path_with_name, "a+", encoding="utf-8") as jv_file:
            jv_file.write(ejv_content)
            jv_file.close()
        # TRG File
        with open(trg_file_path, "a+", encoding="utf-8") as trg_file:
            trg_file.write("")
            trg_file.close()
        return file_path_with_name, trg_file_path, file_name
