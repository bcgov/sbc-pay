# Copyright © 2023 Province of British Columbia
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
"""Service to manage EFT GL Transfers."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func

from pay_api.models import EFTGLTransfer as EFTGLTransferModel
from pay_api.models import db


@dataclass
class EFTGlTransferSearch:  # pylint: disable=too-many-instance-attributes
    """Used for searching EFT GL Transfer records."""

    created_on: Optional[datetime] = None
    invoice_id: Optional[int] = None
    is_processed: Optional[bool] = None
    processed_on: Optional[datetime] = None
    short_name_id: Optional[int] = None
    source_gl: Optional[str] = None
    target_gl: Optional[str] = None
    transfer_type: Optional[str] = None
    transfer_date: Optional[datetime] = None


class EFTGlTransfer:
    """Service to manage EFT GL transfers."""

    @staticmethod
    def find_by_id(transfer_id: int) -> EFTGLTransferModel:
        """Return EFT Transfers by id."""
        return EFTGLTransferModel.find_by_id(transfer_id)

    @staticmethod
    def find_by_short_name_id(short_name_id: int, is_processed: bool = None) -> [EFTGLTransferModel]:
        """Return EFT Transfers by short_name_id."""
        query = db.session.query(EFTGLTransferModel) \
            .filter(EFTGLTransferModel.short_name_id == short_name_id)

        if is_processed is not None:
            query = query.filter(EFTGLTransferModel.is_processed == is_processed) \

        query = query.order_by(EFTGLTransferModel.created_on.asc())

        return query.all()

    @staticmethod
    def find_by_invoice_id(invoice_id: int, is_processed: bool = None) -> [EFTGLTransferModel]:
        """Return EFT Transfers by invoice_id."""
        query = db.session.query(EFTGLTransferModel) \
            .filter(EFTGLTransferModel.invoice_id == invoice_id)

        if is_processed is not None:
            query = query.filter(EFTGLTransferModel.is_processed == is_processed)

        query = query.order_by(EFTGLTransferModel.created_on.asc())

        return query.all()

    @staticmethod
    def search(search_criteria: EFTGlTransferSearch = EFTGlTransferSearch()) -> [EFTGLTransferModel]:
        """Return EFT Transfers by search criteria."""
        query = db.session.query(EFTGLTransferModel)

        if search_criteria.created_on:
            query = query.filter(func.DATE(EFTGLTransferModel.created_on) == search_criteria.created_on.date())

        if search_criteria.invoice_id:
            query = query.filter(EFTGLTransferModel.invoice_id == search_criteria.invoice_id)

        if search_criteria.is_processed is not None:
            query = query.filter(EFTGLTransferModel.is_processed == search_criteria.is_processed)

        if search_criteria.processed_on:
            query = query.filter(func.DATE(EFTGLTransferModel.processed_on) == search_criteria.processed_on.date())

        if search_criteria.short_name_id:
            query = query.filter(EFTGLTransferModel.short_name_id == search_criteria.short_name_id)

        if search_criteria.source_gl:
            query = query.filter(EFTGLTransferModel.source_gl == search_criteria.source_gl)

        if search_criteria.target_gl:
            query = query.filter(EFTGLTransferModel.target_gl == search_criteria.target_gl)

        if search_criteria.transfer_type:
            query = query.filter(EFTGLTransferModel.transfer_type == search_criteria.transfer_type)

        if search_criteria.transfer_date:
            query = query.filter(func.DATE(EFTGLTransferModel.transfer_date) == search_criteria.transfer_date.date())

        query = query.order_by(EFTGLTransferModel.created_on.asc())

        return query.all()
