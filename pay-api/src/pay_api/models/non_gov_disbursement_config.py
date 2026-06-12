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
"""Model for per-partner CAS supplier credentials used in non-government AP disbursements."""

from sqlalchemy import Boolean, ForeignKey

from .audit import Audit
from .db import db


class NonGovDisbursementConfig(Audit):
    """CAS supplier details for non-government partners paid via AP/EFT through CGI."""

    __tablename__ = "non_gov_disbursement_config"

    __mapper_args__ = {
        "include_properties": [
            "corp_type_code",
            "cas_supplier_number",
            "cas_supplier_site",
            "disabled",
            "created_by",
            "created_name",
            "created_on",
            "updated_by",
            "updated_name",
            "updated_on",
        ]
    }

    corp_type_code = db.Column(db.String(10), ForeignKey("corp_types.code"), primary_key=True)
    cas_supplier_number = db.Column(db.String(50), nullable=True)
    cas_supplier_site = db.Column(db.String(10), nullable=True)
    disabled = db.Column(Boolean, nullable=False, default=False)
