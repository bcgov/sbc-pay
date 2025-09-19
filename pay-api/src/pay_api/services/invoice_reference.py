# Copyright © 2024 Province of British Columbia
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
"""Service to manage Invoice Reference."""

from flask import current_app

from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.utils.enums import InvoiceReferenceStatus


class InvoiceReference:
    """Service to manage Invoice Reference related operations."""

    @staticmethod
    def create(invoice_id: int, invoice_number: str, reference_number: str) -> InvoiceReferenceModel:
        """Create invoice reference record."""
        current_app.logger.debug("<create")
        i = InvoiceReferenceModel()
        i.invoice_id = invoice_id
        i.status_code = InvoiceReferenceStatus.ACTIVE.value
        i.invoice_number = invoice_number
        i.reference_number = reference_number
        i.save()
        current_app.logger.debug(">create")
        return i

    @staticmethod
    def find_active_reference_by_invoice_id(inv_id: int) -> InvoiceReferenceModel:
        """Find invoice reference by invoice id."""
        dao = InvoiceReferenceModel.find_by_invoice_id_and_status(inv_id, InvoiceReferenceStatus.ACTIVE.value)
        current_app.logger.debug(">find_reference_by_invoice_id")
        return dao

    @staticmethod
    def find_completed_reference_by_invoice_id(inv_id: int) -> InvoiceReferenceModel:
        """Find invoice reference by invoice id."""
        dao = InvoiceReferenceModel.find_by_invoice_id_and_status(inv_id, InvoiceReferenceStatus.COMPLETED.value)
        current_app.logger.debug(">find_reference_by_invoice_id")
        return dao

    @staticmethod
    def find_any_active_reference_by_invoice_number(inv_number: str) -> InvoiceReferenceModel:
        """Find invoice reference by invoice id."""
        dao = InvoiceReferenceModel.find_any_active_reference_by_invoice_number(inv_number)
        current_app.logger.debug(">find_any_active_reference_by_invoice_number")
        return dao
