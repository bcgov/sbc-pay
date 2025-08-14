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
"""Service to manage Receipt."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from flask import current_app

from pay_api.exceptions import BusinessException
from pay_api.factory.payment_system_factory import PaymentSystemFactory
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import PaymentMethod as PaymentMethodModel
from pay_api.models import Refund as RefundModel
from pay_api.models import RefundPartialLine
from pay_api.models import RefundsPartial as RefundPartialModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import db
from pay_api.services.base_payment_system import PaymentSystemService
from pay_api.services.partner_disbursements import PartnerDisbursements
from pay_api.services.payment_account import PaymentAccount
from pay_api.utils.constants import REFUND_SUCCESS_MESSAGES
from pay_api.utils.converter import Converter
from pay_api.utils.enums import (
    ChequeRefundStatus,
    CorpType,
    InvoiceStatus,
    PaymentMethod,
    RefundsPartialStatus,
    RefundsPartialType,
    Role,
    RoutingSlipStatus,
    TransactionStatus,
)
from pay_api.utils.errors import Error
from pay_api.utils.user_context import UserContext, user_context
from pay_api.utils.util import get_quantized, get_str_by_path, normalize_accented_characters_json


class RefundService:
    """Service to hold and manage refund instance."""

    @classmethod
    @user_context
    def create_routing_slip_refund(cls, routing_slip_number: str, request: Dict[str, str], **kwargs) -> Dict[str, str]:
        """Create Routing slip refund."""
        current_app.logger.debug("<create Routing slip refund")
        #
        # check if routing slip exists
        # validate user role -> update status of routing slip
        # check refunds table
        #   if Yes ; update the data [only with whatever is in payload]
        #   if not ; create new entry
        # call cfs
        rs_model = RoutingSlipModel.find_by_number(routing_slip_number)
        if not rs_model:
            raise BusinessException(Error.RS_DOESNT_EXIST)
        reason = get_str_by_path(request, "reason")
        if (status := get_str_by_path(request, "status")) is None:
            raise BusinessException(Error.INVALID_REQUEST)
        user_name = kwargs["user"].user_name
        if get_quantized(rs_model.remaining_amount) == 0:
            raise BusinessException(Error.INVALID_REQUEST)  # refund not possible for zero amount routing slips

        is_refund_finalized = status in (
            RoutingSlipStatus.REFUND_AUTHORIZED.value,
            RoutingSlipStatus.REFUND_REJECTED.value,
        )
        if is_refund_finalized:
            RefundService._is_authorised_refund()

        # Rejected refund makes routing slip active
        if status == RoutingSlipStatus.REFUND_REJECTED.value:
            status = RoutingSlipStatus.ACTIVE.value
            rs_model.refund_status = None
            reason = f"Refund Rejected by {user_name}"
        else:
            rs_model.refund_status = ChequeRefundStatus.PROCESSING

        rs_model.status = status
        rs_model.flush()

        refund = RefundModel.find_by_routing_slip_id(rs_model.id) or RefundModel()

        if not is_refund_finalized:
            # do not update these for approval/rejections
            refund.routing_slip_id = rs_model.id
            refund.requested_by = kwargs["user"].user_name
            refund.requested_date = datetime.now(tz=timezone.utc)
        else:
            refund.decision_made_by = kwargs["user"].user_name
            refund.decision_date = datetime.now(tz=timezone.utc)

        refund.reason = reason
        if details := request.get("details"):
            refund.details = normalize_accented_characters_json(details)

        refund.save()
        message = REFUND_SUCCESS_MESSAGES.get(f"ROUTINGSLIP.{rs_model.status}")
        return {"message": message}

    @staticmethod
    @user_context
    def _is_authorised_refund(**kwargs):
        user: UserContext = kwargs["user"]
        has_refund_approver_role = Role.FAS_REFUND_APPROVER.value in user.roles
        if not has_refund_approver_role:
            raise BusinessException(Error.INVALID_REQUEST)

    @staticmethod
    def _get_line_item_amount_by_refund_type(refund_type: str, payment_line_item: PaymentLineItemModel):
        """Return payment line item fee amount by refund type."""
        match refund_type:
            case RefundsPartialType.BASE_FEES.value:
                return payment_line_item.filing_fees
            case RefundsPartialType.FUTURE_EFFECTIVE_FEES.value:
                return payment_line_item.future_effective_fees
            case RefundsPartialType.SERVICE_FEES.value:
                return payment_line_item.service_fees
            case RefundsPartialType.PRIORITY_FEES.value:
                return payment_line_item.priority_fees
            case _:
                return 0

    @staticmethod
    def _validate_refund_amount(refund_line: RefundPartialLine, payment_line_item: PaymentLineItemModel):
        """Validate refund amount does not exceed line item amount and is positive."""
        threshold_amount = RefundService._get_line_item_amount_by_refund_type(
            refund_line.refund_type, payment_line_item
        )
        refund_amount = refund_line.refund_amount

        if refund_amount < 0 or refund_amount > threshold_amount:
            raise BusinessException(Error.REFUND_AMOUNT_INVALID)

    @staticmethod
    def _validate_partial_refund_lines(refund_revenue: List[RefundPartialLine], invoice: InvoiceModel):
        """Validate partial refund line amounts."""
        for refund_line in refund_revenue:
            payment_line: PaymentLineItemModel = next(
                (
                    line_item
                    for line_item in invoice.payment_line_items
                    if line_item.id == refund_line.payment_line_item_id
                ),
                None,
            )
            if refund_line.refund_type == RefundsPartialType.SERVICE_FEES.value:
                raise BusinessException(Error.PARTIAL_REFUND_SERVICE_FEES_NOT_ALLOWED)
            if payment_line is None:
                raise BusinessException(Error.REFUND_PAYMENT_LINE_ITEM_INVALID)
            RefundService._validate_refund_amount(refund_line, payment_line)

    @classmethod
    def _validate_allow_partial_refund(cls, invoice: InvoiceModel):
        if not PaymentMethodModel.is_partial_refund_allowed(invoice.payment_method_code):
            raise BusinessException(Error.PARTIAL_REFUND_PAYMENT_METHOD_UNSUPPORTED)

        if invoice.invoice_status_code != InvoiceStatus.PAID.value:
            raise BusinessException(Error.PARTIAL_REFUND_INVOICE_NOT_PAID)

    @classmethod
    def _validate_allow_full_refund(cls, invoice: InvoiceModel):
        if not PaymentMethodModel.is_full_refund_allowed(invoice.payment_method_code, invoice.invoice_status_code):
            raise BusinessException(Error.FULL_REFUND_INVOICE_INVALID_STATE)

    @classmethod
    def _validate_corp_type_role(cls, invoice: InvoiceModel, roles: list):
        if roles and Role.CSO_REFUNDS.value in roles:
            if invoice.corp_type_code != CorpType.CSO.value:
                raise BusinessException(Error.INVALID_REQUEST)

    @classmethod
    def _validate_refundable_state(cls, invoice: InvoiceModel, is_partial: bool):
        if is_partial:
            cls._validate_allow_partial_refund(invoice)
        else:
            cls._validate_allow_full_refund(invoice)

        if invoice.refund_date is not None:
            current_app.logger.info(
                f"Cannot process refund as status of {invoice.id} is {invoice.invoice_status_code}."
                "Refund date already set."
            )
            raise BusinessException(Error.INVALID_REQUEST)

    @classmethod
    def _initialize_refund(cls, invoice_id: int, request: Dict[str, str], user: UserContext) -> RefundModel:
        """Initialize refund."""
        refund = RefundModel()
        refund.invoice_id = invoice_id
        refund.reason = get_str_by_path(request, "reason")
        refund.requested_by = user.user_name
        refund.requested_date = datetime.now(tz=timezone.utc)
        refund.flush()

        return refund

    @classmethod
    @user_context
    def create_refund(cls, invoice_id: int, request: Dict[str, str], **kwargs) -> Dict[str, str]:
        """Create refund."""
        current_app.logger.debug(f"Starting refund : {invoice_id}")
        user: UserContext = kwargs["user"]
        refund_revenue = (request or {}).get("refundRevenue", None)
        is_partial_refund = bool(refund_revenue)
        refund_partial_lines = []

        invoice = InvoiceModel.find_by_id(invoice_id)
        cls._validate_corp_type_role(invoice, user.roles)
        cls._validate_refundable_state(invoice, is_partial_refund)

        payment_account = PaymentAccount.find_by_id(invoice.payment_account_id)
        pay_system_service: PaymentSystemService = PaymentSystemFactory.create_from_payment_method(
            payment_method=invoice.payment_method_code
        )

        if is_partial_refund:
            refund_partial_lines = cls._get_partial_refund_lines(refund_revenue)
            cls._validate_partial_refund_lines(refund_partial_lines, invoice)

        invoice.refund = (
            pay_system_service.get_total_partial_refund_amount(refund_partial_lines)
            if is_partial_refund
            else invoice.total
        )
        invoice_status = pay_system_service.process_cfs_refund(
            invoice,
            payment_account=payment_account,
            refund_partial=refund_partial_lines,
        )

        refund = cls._initialize_refund(invoice_id, request, user)
        cls._save_partial_refund_lines(refund_partial_lines, invoice)
        message = REFUND_SUCCESS_MESSAGES.get(f"{invoice.payment_method_code}.{invoice.invoice_status_code}")
        invoice.invoice_status_code = invoice_status or InvoiceStatus.REFUND_REQUESTED.value

        if invoice.invoice_status_code in (
            InvoiceStatus.REFUNDED.value,
            InvoiceStatus.CANCELLED.value,
            InvoiceStatus.CREDITED.value,
            InvoiceStatus.PAID.value,
        ):
            invoice.refund_date = datetime.now(tz=timezone.utc)
        invoice.save()

        # Exclude PAID because it's for partial refunds.
        if invoice.invoice_status_code in (
            InvoiceStatus.REFUNDED.value,
            InvoiceStatus.CANCELLED.value,
            InvoiceStatus.CREDITED.value,
        ):
            pay_system_service.release_payment_or_reversal(invoice, TransactionStatus.REVERSED.value)
        elif invoice.invoice_status_code == InvoiceStatus.PAID.value:
            pay_system_service.release_payment_or_reversal(invoice, TransactionStatus.PARTIALLY_REVERSED.value)
        current_app.logger.debug(f"Completed refund : {invoice_id}")

        return {
            "message": message,
            "refundId": refund.id,
            "refundAmount": invoice.refund,
            "isPartialRefund": is_partial_refund,
        }

    @staticmethod
    def _save_partial_refund_lines(partial_refund_lines: List[RefundPartialLine], invoice: InvoiceModel):
        """Persist a list of partial refund lines."""
        for line in partial_refund_lines:
            refund_line = RefundPartialModel(
                invoice_id=invoice.id,
                payment_line_item_id=line.payment_line_item_id,
                refund_amount=line.refund_amount,
                refund_type=line.refund_type,
                status=(
                    RefundsPartialStatus.REFUND_REQUESTED.value
                    if invoice.payment_method_code in (PaymentMethod.INTERNAL.value)
                    else RefundsPartialStatus.REFUND_PROCESSED.value
                ),
                # Anything in AR module is a credit
                is_credit=invoice.payment_method_code
                in (
                    PaymentMethod.PAD.value,
                    PaymentMethod.ONLINE_BANKING.value,
                    PaymentMethod.INTERNAL.value,
                    PaymentMethod.EFT.value,
                ),
            )
            db.session.add(refund_line)

            PartnerDisbursements.handle_partial_refund(refund_line, invoice)

    @staticmethod
    def _get_partial_refund_lines(
        refund_revenue: List[Dict],
    ) -> List[RefundPartialLine]:
        """Convert Refund revenue data to a list of Partial Refund lines."""
        if not refund_revenue:
            return []

        return Converter(camel_to_snake_case=True, enum_to_value=True).structure(
            refund_revenue, List[RefundPartialLine]
        )

    @staticmethod
    def get_refund_partials_by_invoice_id(invoice_id: int):
        """Return refund partials by invoice id."""
        return (
            db.session.query(RefundPartialModel)
            .join(
                PaymentLineItemModel,
                PaymentLineItemModel.id == RefundPartialModel.payment_line_item_id,
            )
            .filter(PaymentLineItemModel.invoice_id == invoice_id)
            .all()
        )

    @staticmethod
    def get_refund_partials_by_payment_line_item_id(payment_line_item_id: int):
        """Return refund partials by payment line item id."""
        return db.session.query(RefundPartialModel).filter(PaymentLineItemModel.id == payment_line_item_id).all()
