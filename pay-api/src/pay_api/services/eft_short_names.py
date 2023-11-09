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
"""Service to manage EFT short name model operations."""
from __future__ import annotations

from datetime import datetime
from operator import and_
from typing import Any, Dict, List, Optional

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.factory.payment_system_factory import PaymentSystemFactory
from pay_api.models import EFTCredit as EFTCreditModel
from pay_api.models import EFTShortnames as EFTShortnameModel
from pay_api.models import EFTShortnameSchema
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import db
from pay_api.utils.enums import InvoiceStatus, PaymentMethod
from pay_api.utils.errors import Error


class EFTShortnames:  # pylint: disable=too-many-instance-attributes
    """Service to manage EFT short name model operations."""

    def __init__(self):
        """Initialize service."""
        self.__dao = None
        self._id: Optional[int] = None
        self._auth_account_id: Optional[str] = None
        self._short_name: Optional[str] = None
        self._created_on: Optional[datetime] = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = EFTShortnameModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value: EFTShortnameModel):
        self.__dao = value
        self.id: int = self._dao.id
        self.auth_account_id: str = self._dao.auth_account_id
        self.short_name: str = self._dao.short_name

    @property
    def id(self):
        """Return the _id."""
        return self._id

    @id.setter
    def id(self, value: int):
        """Set the id."""
        self._id = value
        self._dao.id = value

    @property
    def auth_account_id(self):
        """Return the auth_account_id."""
        return self._auth_account_id

    @auth_account_id.setter
    def auth_account_id(self, value: str):
        """Set the auth_account_id."""
        self._auth_account_id = value
        self._dao.auth_account_id = value

    @property
    def short_name(self):
        """Return the short name."""
        return self._short_name

    @short_name.setter
    def short_name(self, value: str):
        """Set the short name."""
        self._short_name = value
        self._dao.short_name = value

    @property
    def created_on(self):
        """Return the created_on date."""
        return self._created_on

    @created_on.setter
    def created_on(self, value: datetime):
        """Set the created on date."""
        self._created_on = value
        self._dao.created_on = value

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    def flush(self):
        """Flush the information to the DB."""
        return self._dao.flush()

    @classmethod
    def create(cls, short_name_request: Dict[str, Any] = None) -> EFTShortnames:
        """Create new eft short name record."""
        current_app.logger.debug('<create eft short name')
        short_name = short_name_request.get('shortName')
        # If a short name already exists, throw error.
        if EFTShortnameModel.find_by_short_name(short_name):
            raise BusinessException(Error.EFT_SHORT_NAME_EXISTS)

        short_name_model = EFTShortnameModel()
        EFTShortnames._save(short_name_request, short_name_model)

        eft_short_name = EFTShortnames()
        eft_short_name._dao = short_name_model  # pylint: disable=protected-access

        current_app.logger.debug('>create eft short name')
        return eft_short_name

    @classmethod
    def _save(cls, short_name_request: Dict[str, any], short_name: EFTShortnameModel):
        """Update and save eft short name model."""
        short_name.short_name = short_name_request.get('shortName')
        short_name.auth_account_id = short_name_request.get('accountId', None)
        short_name.flush()
        short_name.save()

    @classmethod
    def update(cls, short_name_id: str, short_name_request: Dict[str, Any]) -> EFTShortnames:
        """Create or update payment account record."""
        current_app.logger.debug('<update eft short name mapping')

        short_name = EFTShortnameModel.find_by_id(short_name_id)
        if short_name is None:
            short_name = EFTShortnameModel()

        EFTShortnames._save(short_name_request, short_name)

        current_app.logger.debug('>update short name mapping')
        return cls.find_by_short_name_id(short_name.id)

    @classmethod
    def patch(cls, short_name_id: int, auth_account_id: str) -> EFTShortnames:
        """Patch eft short name auth account mapping."""
        current_app.logger.debug('<patch eft short name mapping')

        short_name: EFTShortnameModel = EFTShortnameModel.find_by_id(short_name_id)
        if auth_account_id is None:
            raise BusinessException(Error.EFT_SHORT_NAME_ACCOUNT_ID_REQUIRED)

        # If a short name has already been mapped, there could be payments already made.
        if short_name.auth_account_id is not None:
            raise BusinessException(Error.EFT_SHORT_NAME_ALREADY_MAPPED)

        short_name.auth_account_id = auth_account_id
        short_name.save()

        # Update any existing credit mappings with the payment account
        payment_account = PaymentAccountModel.find_by_auth_account_id(auth_account_id)
        EFTCreditModel.update_account_by_short_name_id(short_name_id, payment_account.id)

        # Process any invoices owing for short name mapping
        cls.process_owing_invoices(short_name_id)

        current_app.logger.debug('>patch short name mapping')
        return cls.find_by_short_name_id(short_name.id)

    @staticmethod
    def process_owing_invoices(short_name_id: int) -> EFTShortnames:
        """Process outstanding invoices when an EFT short name is mapped to an auth account id using credits."""
        current_app.logger.debug('<process_outstanding_invoices')
        short_name_model: EFTShortnameModel = EFTShortnameModel.find_by_id(short_name_id)
        auth_account_id = short_name_model.auth_account_id

        # Find invoices to be paid
        invoices: List[InvoiceModel] = EFTShortnames.get_invoices_owing(auth_account_id)
        pay_service = PaymentSystemFactory.create_from_payment_method(PaymentMethod.EFT.value)

        if invoices is not None:
            for invoice in invoices:
                pay_service.apply_credit(invoice)

        current_app.logger.debug('>process_outstanding_invoices')

    @staticmethod
    def get_invoices_owing(auth_account_id: str) -> [InvoiceModel]:
        """Return invoices that have not been fully paid."""
        unpaid_status = (InvoiceStatus.PARTIAL.value,
                         InvoiceStatus.CREATED.value, InvoiceStatus.OVERDUE.value)
        query = db.session.query(InvoiceModel) \
            .join(PaymentAccountModel, and_(PaymentAccountModel.id == InvoiceModel.payment_account_id,
                                            PaymentAccountModel.auth_account_id == auth_account_id)) \
            .filter(InvoiceModel.invoice_status_code.in_(unpaid_status)) \
            .filter(InvoiceModel.payment_method_code == PaymentMethod.EFT.value) \
            .order_by(InvoiceModel.created_on.asc())

        return query.all()

    @classmethod
    def find_by_short_name_id(cls, short_name_id: int) -> EFTShortnames:
        """Find payment account by corp number, corp type and payment system code."""
        current_app.logger.debug('<find_by_short_name_id')
        short_name_model: EFTShortnameModel = EFTShortnameModel.find_by_id(short_name_id)
        short_name_service = None
        if short_name_model:
            short_name_service = EFTShortnames()
            short_name_service._dao = short_name_model  # pylint: disable=protected-access
            current_app.logger.debug('>find_by_short_name_id')
        return short_name_service

    @staticmethod
    def search(include_all: bool, page: int, limit: int):
        """Find all eft short name records."""
        current_app.logger.debug('<search')
        short_names, total = EFTShortnameModel.find_all_short_names(include_all, page, limit)
        short_names_schema = EFTShortnameSchema()
        data = {
            'total': total,
            'page': page,
            'limit': limit,
            'items': short_names_schema.dump(short_names, many=True)
        }
        current_app.logger.debug('>search')
        return data

    def asdict(self):
        """Return the EFT Short name as a python dict."""
        short_name_schema = EFTShortnameSchema()
        d = short_name_schema.dump(self._dao)
        return d
