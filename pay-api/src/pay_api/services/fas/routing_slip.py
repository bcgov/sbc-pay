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
"""Service to manage routing slip operations."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Dict, List

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import RoutingSlipSchema
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import (
    AuthHeaderType, CfsAccountStatus, ContentType, PatchActions, PaymentMethod, PaymentStatus, PaymentSystem,
    RoutingSlipStatus)
from pay_api.utils.errors import Error
from pay_api.utils.user_context import user_context
from pay_api.utils.util import get_local_time, string_to_date


class RoutingSlip:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Service to manage Routing slip related operations."""

    def __init__(self):
        """Initialize the service."""
        self.__dao = None
        self._id: int = None
        self._number: str = None
        self._payment_account_id: int = None
        self._status_code: str = None
        self._total: Decimal = None
        self._remaining_amount: Decimal = None

    @property
    def _dao(self):
        if not self.__dao:
            self.__dao = RoutingSlipModel()
        return self.__dao

    @_dao.setter
    def _dao(self, value):
        self.__dao: RoutingSlipModel = value
        self.id: int = self._dao.id
        self.number: str = self._dao.number
        self.status_code: str = self._dao.status_code
        self.payment_account_id: int = self._dao.payment_account_id
        self.total: Decimal = self._dao.total
        self.remaining_amount: Decimal = self._dao.remaining_amount

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
    def number(self):
        """Return the number."""
        return self._number

    @number.setter
    def number(self, value: str):
        """Set the number."""
        self._number = value
        self._dao.number = value

    @property
    def status_code(self):
        """Return the status_code."""
        return self._status_code

    @status_code.setter
    def status_code(self, value: str):
        """Set the status_code."""
        self._status_code = value
        self._dao.status_code = value

    @property
    def payment_account_id(self):
        """Return the payment_account_id."""
        return self._payment_account_id

    @payment_account_id.setter
    def payment_account_id(self, value: int):
        """Set the payment_account_id."""
        self._payment_account_id = value
        self._dao.payment_account_id = value

    @property
    def total(self):
        """Return the total."""
        return self._total

    @total.setter
    def total(self, value: Decimal):
        """Set the total."""
        self._total = value
        self._dao.total = value

    @property
    def remaining_amount(self):
        """Return the remaining_amount."""
        return self._remaining_amount

    @remaining_amount.setter
    def remaining_amount(self, value: Decimal):
        """Set the amount."""
        self._remaining_amount = value
        self._dao.remaining_amount = value

    def commit(self):
        """Save the information to the DB."""
        return self._dao.commit()

    def flush(self):
        """Save the information to the DB."""
        return self._dao.flush()

    def rollback(self):
        """Rollback."""
        return self._dao.rollback()

    def save(self):
        """Save the information to the DB."""
        return self._dao.save()

    def asdict(self) -> Dict[str]:
        """Return the routing slip as a python dict."""
        routing_slip_schema = RoutingSlipSchema()
        d = routing_slip_schema.dump(self._dao)
        return d

    @classmethod
    def search(cls, search_filter: Dict, page: int, limit: int, return_all: bool = False):
        """Search for routing slip."""
        max_no_records: int = 0
        if not bool(search_filter) or not any(search_filter.values()):
            max_no_records = current_app.config.get('ROUTING_SLIP_DEFAULT_TOTAL')

        routing_slips, total = RoutingSlipModel.search(search_filter, page, limit, return_all,
                                                       max_no_records)
        data = {
            'total': total,
            'page': page,
            'limit': limit,
            'items': RoutingSlipSchema().dump(routing_slips, many=True)
        }

        return data

    @classmethod
    @user_context
    def create_daily_reports(cls, date: str, **kwargs):
        """Create and return daily report for the day provided."""
        routing_slips: List[RoutingSlipModel] = RoutingSlipModel.search(
            dict(
                dateFilter=dict(
                    endDate=date,
                    startDate=date,
                    target='created_on'
                )
            ),
            page=1, limit=0, return_all=True
        )[0]

        total: float = 0
        no_of_cash: int = 0
        no_of_cheque: int = 0
        total_cash_usd: float = 0
        total_cheque_usd: float = 0
        total_cash_cad: float = 0
        total_cheque_cad: float = 0
        # TODO Only CAD supported now, so just add up the total.
        for routing_slip in routing_slips:
            total += float(routing_slip.total)
            if routing_slip.payment_account.payment_method == PaymentMethod.CASH.value:
                no_of_cash += 1
                # TODO check if the payment is CAD or USD.
                total_cash_cad += float(routing_slip.total)
            else:
                no_of_cheque += 1
                total_cheque_cad += float(routing_slip.total)

        report_dict = dict(
            templateName='routing_slip_report',
            reportName=f'Routing-Slip-Daily-Report-{date}',
            templateVars=dict(
                day=date,
                reportDay=str(get_local_time(datetime.now())),
                total=total,
                numberOfCashReceipts=no_of_cash,
                numberOfChequeReceipts=no_of_cheque,
                totalCashInUsd=total_cash_usd,
                totalChequeInUsd=total_cheque_usd,
                totalCashInCad=total_cash_cad,
                totalChequeInCad=total_cheque_cad
            )
        )

        pdf_response = OAuthService.post(current_app.config.get('REPORT_API_BASE_URL'),
                                         kwargs['user'].bearer_token, AuthHeaderType.BEARER,
                                         ContentType.JSON, report_dict)

        return pdf_response, report_dict.get('reportName')

    @classmethod
    def find_by_number(cls, rs_number: str) -> Dict[str, any]:
        """Find by routing slip number."""
        routing_slip_dict: Dict[str, any] = None
        routing_slip: RoutingSlipModel = RoutingSlipModel.find_by_number(rs_number)
        if routing_slip:
            routing_slip_schema = RoutingSlipSchema()
            routing_slip_dict = routing_slip_schema.dump(routing_slip)
        return routing_slip_dict

    @classmethod
    def get_links(cls, rs_number: str) -> Dict[str, any]:
        """Find dependents/links of a routing slips."""
        links: Dict[str, any] = None
        routing_slip: RoutingSlipModel = RoutingSlipModel.find_by_number(rs_number)
        if routing_slip:
            routing_slip_schema = RoutingSlipSchema()
            children = RoutingSlipModel.find_children(rs_number)
            links = {
                'parent': routing_slip_schema.dump(routing_slip.parent),
                'children': routing_slip_schema.dump(children, many=True)
            }

        return links

    @classmethod
    @user_context
    def create(cls, request_json: Dict[str, any], **kwargs):
        """Search for routing slip."""
        # 1. Create customer profile in CFS and store it in payment_account and cfs_accounts
        # 2. Create receipt in CFS
        # 3. Create routing slip and payment records.

        # Validate if Routing slip number is unique.
        rs_number = request_json.get('number')
        if cls.find_by_number(rs_number):
            raise BusinessException(Error.FAS_INVALID_ROUTING_SLIP_NUMBER)

        payment_methods: [str] = [payment.get('paymentMethod') for payment in request_json.get('payments')]
        # all the payment should have the same payment method
        if len(set(payment_methods)) != 1:
            raise BusinessException(Error.FAS_INVALID_PAYMENT_METHOD)

        pay_account: PaymentAccountModel = PaymentAccountModel(
            name=request_json.get('paymentAccount').get('accountName'),
            payment_method=payment_methods[0],
        ).flush()

        CfsAccountModel(
            account_id=pay_account.id,
            status=CfsAccountStatus.PENDING.value
        ).flush()

        total = sum(float(payment.get('paidAmount')) for payment in request_json.get('payments'))

        # Create a routing slip record.
        routing_slip: RoutingSlipModel = RoutingSlipModel(
            number=rs_number,
            payment_account_id=pay_account.id,
            status=RoutingSlipStatus.ACTIVE.value,
            total=total,
            remaining_amount=total,
            routing_slip_date=string_to_date(request_json.get('routingSlipDate'))
        ).flush()

        for payment in request_json.get('payments'):
            PaymentModel(
                payment_system_code=PaymentSystem.FAS.value,
                payment_account_id=pay_account.id,
                payment_method_code=payment.get('paymentMethod'),
                payment_status_code=PaymentStatus.COMPLETED.value,
                receipt_number=rs_number,
                cheque_receipt_number=payment.get('chequeReceiptNumber'),
                is_routing_slip=True,
                paid_amount=payment.get('paidAmount'),
                payment_date=string_to_date(payment.get('paymentDate')) if payment.get('paymentDate') else None,
                created_by=kwargs['user'].user_name
            ).flush()

        routing_slip.commit()
        return cls.find_by_number(rs_number)

    @classmethod
    def do_link(cls, rs_number: str, parent_rs_number: str) -> Dict[str, any]:
        """Link routing slip to parent routing slip."""
        routing_slip: RoutingSlipModel = RoutingSlipModel.find_by_number(rs_number)
        parent_routing_slip: RoutingSlipModel = RoutingSlipModel.find_by_number(parent_rs_number)
        if routing_slip is None or parent_routing_slip is None:
            raise BusinessException(Error.FAS_INVALID_ROUTING_SLIP_NUMBER)

        # do validations if its linkable
        RoutingSlip._validate_linking(routing_slip=routing_slip, parent_rs_slip=parent_routing_slip)

        routing_slip.parent_number = parent_routing_slip.number
        routing_slip.status = RoutingSlipStatus.LINKED.value

        # transfer the amount to parent.
        # we keep the total amount as such and transfer only the remaining amount.
        parent_routing_slip.remaining_amount += routing_slip.remaining_amount
        routing_slip.remaining_amount = 0

        routing_slip.commit()
        return cls.find_by_number(rs_number)

    @classmethod
    def update(cls, rs_number: str, action: str, request_json: Dict[str, any]) -> Dict[str, any]:
        """Update routing slip."""
        if (patch_action := PatchActions.from_value(action)) is None:
            raise BusinessException(Error.PATCH_INVALID_ACTION)

        routing_slip: RoutingSlipModel = RoutingSlipModel.find_by_number(rs_number)
        if routing_slip is None:
            raise BusinessException(Error.FAS_INVALID_ROUTING_SLIP_NUMBER)

        if patch_action == PatchActions.UPDATE_STATUS:
            # Update the remaining amount as negative total of sum of all totals for that routing slip.
            if (status := request_json.get('status')) == RoutingSlipStatus.NSF.value:
                total_paid_to_reverse: float = 0
                for rs in (routing_slip, *RoutingSlipModel.find_children(routing_slip.number)):
                    total_paid_to_reverse += rs.total
                routing_slip.remaining_amount = -total_paid_to_reverse

            routing_slip.status = status

        routing_slip.save()
        return cls.find_by_number(rs_number)

    @staticmethod
    def _validate_linking(routing_slip: RoutingSlipModel, parent_rs_slip: RoutingSlipModel) -> None:
        """Validate the linking.

        1). child already has a parent/already linked.
        2). its already a parent.
        3). parent_rs_slip has a parent.ie parent_rs_slip shouldn't already be linked
        4). one of them has transactions
        """
        if RoutingSlip._is_linked_already(routing_slip):
            raise BusinessException(Error.RS_ALREADY_LINKED)

        children = RoutingSlipModel.find_children(routing_slip.number)
        if children and len(children) > 0:
            raise BusinessException(Error.RS_ALREADY_A_PARENT)

        if RoutingSlip._is_linked_already(parent_rs_slip):
            raise BusinessException(Error.RS_PARENT_ALREADY_LINKED)

        # prevent self linking

        if routing_slip.number == parent_rs_slip.number:
            raise BusinessException(Error.RS_CANT_LINK_TO_SAME)

        # has one of these has pending
        if routing_slip.invoices:
            raise BusinessException(Error.RS_CHILD_HAS_TRANSACTIONS)

    @staticmethod
    def _is_linked_already(routing_slip: RoutingSlipModel):
        """Find if the rs is already linked."""
        return routing_slip.parent or routing_slip.status == RoutingSlipStatus.LINKED.value
