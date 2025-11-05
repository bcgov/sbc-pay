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

from datetime import UTC, datetime
from decimal import Decimal

from flask import abort, current_app

from pay_api.dtos.refund import RefundPatchRequest  # noqa: TC001
from pay_api.exceptions import BusinessException
from pay_api.factory.payment_system_factory import PaymentSystemFactory
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import PaymentMethod as PaymentMethodModel
from pay_api.models import Refund as RefundModel
from pay_api.models import RefundPartialLine, db
from pay_api.models import RefundsPartial as RefundPartialModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models.refund import PartialRefundLineDTO, RefundDTO
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
    RefundStatus,
    RefundType,
    Role,
    RoutingSlipStatus,
    TransactionStatus,
)
from pay_api.utils.errors import Error
from pay_api.utils.product_auth_util import ProductAuthUtil
from pay_api.utils.user_context import UserContext, user_context
from pay_api.utils.util import (
    get_quantized,
    get_str_by_path,
    is_string_empty,
    normalize_accented_characters_json,
)


class RefundService:
    """Service to hold and manage refund instance."""

    @classmethod
    @user_context
    def create_routing_slip_refund(cls, routing_slip_number: str, request: dict[str, str], **kwargs) -> dict[str, str]:
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

        refund = RefundModel.find_by_routing_slip_id(rs_model.id)
        if refund is None:
            refund = RefundModel(type=RefundType.ROUTING_SLIP.value, status=RefundStatus.APPROVAL_NOT_REQUIRED.value)

        if not is_refund_finalized:
            # do not update these for approval/rejections
            refund.routing_slip_id = rs_model.id
            refund.requested_by = kwargs["user"].user_name
            refund.requested_date = datetime.now(tz=UTC)
        else:
            refund.decision_made_by = kwargs["user"].user_name
            refund.decision_date = datetime.now(tz=UTC)

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
    def find_by_invoice_and_refund_id(invoice_id: int, refund_id: int) -> RefundModel:
        """Find refund by invoice and refund id."""
        return RefundModel.find_by_invoice_and_refund_id(invoice_id, refund_id)

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
    def _validate_partial_refund_lines(refund_revenue: list[RefundPartialLine], invoice: InvoiceModel):
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

    @staticmethod
    def validate_product_authorization(invoice: InvoiceModel, allowed_products: list[str], is_system: bool):
        """Validate if the invoice product is in the allowed product list."""
        if not is_system and allowed_products and invoice.corp_type.product not in allowed_products:
            raise BusinessException(Error.REFUND_INSUFFICIENT_PRODUCT_AUTHORIZATION)

    @classmethod
    def _validate_refund_approval_flow(cls, invoice: InvoiceModel, products: list[str], is_system: bool):
        requires_approval = invoice.corp_type.refund_approval
        if not requires_approval:
            return
        else:
            cls.validate_product_authorization(invoice, products, is_system)

        refund = RefundModel.find_latest_by_invoice_id(invoice.id)
        if refund and refund.status != RefundStatus.DECLINED.value:
            raise BusinessException(Error.REFUND_ALREADY_EXISTS)

    @classmethod
    def _initialize_refund(cls, invoice: InvoiceModel, request: dict[str, str], user: UserContext) -> RefundModel:
        """Initialize refund."""
        refund = RefundModel(
            type=RefundType.INVOICE.value,
            invoice_id=invoice.id,
            reason=get_str_by_path(request, "reason"),
            notification_email=get_str_by_path(request, "notificationEmail"),
            staff_comment=get_str_by_path(request, "staffComment"),
            requested_by=user.original_username if user.original_username else user.user_name,
            requested_date=datetime.now(tz=UTC),
            status=(
                RefundStatus.PENDING_APPROVAL.value
                if invoice.corp_type.refund_approval and not user.is_system()
                else RefundStatus.APPROVAL_NOT_REQUIRED.value
            ),
        )
        refund.flush()
        return refund

    @classmethod
    def _complete_refund(
        cls, invoice: InvoiceModel, refund: RefundModel, refund_partial_lines: list[RefundPartialLine]
    ):
        is_partial_refund = len(refund_partial_lines) > 0
        payment_account = PaymentAccount.find_by_id(invoice.payment_account_id)
        pay_system_service: PaymentSystemService = PaymentSystemFactory.create_from_payment_method(
            payment_method=invoice.payment_method_code
        )

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

        message = REFUND_SUCCESS_MESSAGES.get(f"{invoice.payment_method_code}.{invoice.invoice_status_code}")
        invoice.invoice_status_code = invoice_status or InvoiceStatus.REFUND_REQUESTED.value

        if invoice.invoice_status_code in (
            InvoiceStatus.REFUNDED.value,
            InvoiceStatus.CANCELLED.value,
            InvoiceStatus.CREDITED.value,
            InvoiceStatus.PAID.value,
        ):
            invoice.refund_date = datetime.now(tz=UTC)
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
        current_app.logger.debug(f"Completed refund : {invoice.id}")

        return {
            "message": message,
            "refundId": refund.id,
            "refundAmount": invoice.refund,
            "isPartialRefund": is_partial_refund,
        }

    @classmethod
    @user_context
    def create_refund(cls, invoice_id: int, request: dict[str, str], products: list[str], **kwargs) -> dict[str, str]:
        """Create refund."""
        current_app.logger.debug(f"Starting refund : {invoice_id}")
        user: UserContext = kwargs["user"]
        refund_revenue = (request or {}).get("refundRevenue", None)
        is_partial_refund = bool(refund_revenue)
        refund_partial_lines = []

        invoice = InvoiceModel.find_by_id(invoice_id)
        requires_approval = invoice.corp_type.refund_approval
        cls._validate_corp_type_role(invoice, user.roles)
        cls._validate_refundable_state(invoice, is_partial_refund)
        cls._validate_refund_approval_flow(invoice, products, user.is_system())

        if is_partial_refund:
            refund_partial_lines = cls._get_partial_refund_lines(refund_revenue)
            cls._validate_partial_refund_lines(refund_partial_lines, invoice)

        refund = cls._initialize_refund(invoice, request, user)
        cls._save_partial_refund_lines(refund_partial_lines, invoice, refund)
        refund.save()
        if not requires_approval or user.is_system():
            return cls._complete_refund(invoice, refund, refund_partial_lines)

        return {
            "message": f"Invoice ({invoice.id}) for payment method {invoice.payment_method_code} "
            f"is pending refund approval.",
            "refundId": refund.id,
            "refundAmount": (
                PaymentSystemService.get_total_partial_refund_amount(refund_partial_lines)
                if is_partial_refund
                else invoice.total
            ),
            "isPartialRefund": is_partial_refund,
        }

    @staticmethod
    def _save_partial_refund_lines(
        partial_refund_lines: list[RefundPartialLine], invoice: InvoiceModel, refund: RefundModel
    ):
        """Persist a list of partial refund lines."""
        for line in partial_refund_lines:
            refund_line = RefundPartialModel(
                refund_id=refund.id,
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
        refund_revenue: list[dict],
    ) -> list[RefundPartialLine]:
        """Convert Refund revenue data to a list of Partial Refund lines."""
        if not refund_revenue:
            return []

        return Converter(camel_to_snake_case=True, enum_to_value=True).structure(
            refund_revenue, list[RefundPartialLine]
        )

    @staticmethod
    def get_refund_partials_by_refund_id(refund_id: int):
        """Return refund partials by refund id."""
        return db.session.query(RefundPartialModel).filter(RefundPartialModel.refund_id == refund_id).all()

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

    @classmethod
    def _validate_approve_or_decline_refund(cls, refund: RefundModel, data: RefundPatchRequest, user: UserContext):
        """Validate refund request status change."""
        if refund.status != RefundStatus.PENDING_APPROVAL.value:
            raise BusinessException(Error.REFUND_REQUEST_INVALID_STATE)

        valid_actions = [RefundStatus.APPROVED.value, RefundStatus.DECLINED.value]
        if data.status not in valid_actions:
            raise BusinessException(Error.REFUND_REQUEST_UNSUPPORTED_ACTION)

        if data.status == RefundStatus.DECLINED.value and is_string_empty(data.decline_reason):
            raise BusinessException(Error.REFUND_REQUEST_DECLINE_REASON_REQUIRED)

        if is_string_empty(user.user_name):
            raise BusinessException(Error.REFUND_REQUEST_DECISION_USER_NAME_REQUIRED)

    @staticmethod
    @user_context
    def approve_or_decline_refund(refund: RefundModel, data: RefundPatchRequest, products: list[str], **kwargs):
        """Approve or decline an EFT Refund."""
        user: UserContext = kwargs["user"]
        RefundService._validate_approve_or_decline_refund(refund, data, user)

        invoice = InvoiceModel.find_by_id(refund.invoice_id)
        RefundService.validate_product_authorization(invoice, products, user.is_system())

        refund.status = data.status
        refund.decision_made_by = user.user_name
        refund.decision_date = datetime.now(tz=UTC)
        refund.decline_reason = data.decline_reason if data.status == RefundStatus.DECLINED.value else None

        refund_partial_lines = RefundPartialModel.get_partial_refunds_by_refund_id(refund.id) or []
        if refund.status == RefundStatus.APPROVED.value:
            RefundService._complete_refund(invoice, refund, RefundPartialLine.to_schema(refund_partial_lines))
        refund.save()

        normalized_refund_lines, refund_total = RefundService.normalize_partial_refund_lines(refund_partial_lines)
        if not refund_partial_lines:
            refund_total = invoice.total

        return Converter().unstructure(
            RefundDTO.from_row(
                refund, invoice.total, invoice.payment_method_code, normalized_refund_lines, refund_total
            )
        )

    @staticmethod
    def normalize_partial_refund_lines(partial_refund_lines: list[RefundPartialModel]):
        """Convert refund partial models to schema DTO."""
        payment_line_items: dict[int, list[RefundPartialModel]] = {}
        refund_lines = []
        refund_total = Decimal(0)
        for partial_refund_line in partial_refund_lines:
            payment_line_items.setdefault(partial_refund_line.payment_line_item_id, [])
            payment_line_items[partial_refund_line.payment_line_item_id].append(partial_refund_line)

        for line_item_id, line_items in payment_line_items.items():
            line_item_dto = PartialRefundLineDTO(
                payment_line_item_id=line_item_id,
                statutory_fee_amount=Decimal(0),
                future_effective_fee_amount=Decimal(0),
                priority_fee_amount=Decimal(0),
                service_fee_amount=Decimal(0),
            )
            for refund_line in line_items:
                match refund_line.refund_type:
                    case RefundsPartialType.BASE_FEES.value:
                        line_item_dto.statutory_fee_amount = refund_line.refund_amount
                    case RefundsPartialType.SERVICE_FEES.value:
                        line_item_dto.service_fee_amount = refund_line.refund_amount
                    case RefundsPartialType.PRIORITY_FEES.value:
                        line_item_dto.priority_fee_amount = refund_line.refund_amount
                    case RefundsPartialType.FUTURE_EFFECTIVE_FEES.value:
                        line_item_dto.future_effective_fee_amount = refund_line.refund_amount
                refund_total += refund_line.refund_amount
            refund_lines.append(line_item_dto)

        return refund_lines, refund_total

    @staticmethod
    @user_context
    def check_refund_auth(role_pattern: str, all_products_role: str, **kwargs):
        """Check refund authorizations based on product roles."""
        products, filter_by_product = ProductAuthUtil.check_products_from_role_pattern(
            role_pattern=role_pattern, all_products_role=all_products_role
        )
        if filter_by_product:
            if not products:
                abort(403)
            return products, filter_by_product

        user: UserContext = kwargs["user"]
        roles = user.roles or []

        # Authorized if there is one of the defined roles
        is_authorized = (
            len(
                list(
                    {Role.SYSTEM.value, Role.CREATE_CREDITS.value, Role.FAS_REFUND.value, all_products_role}
                    & set(roles)
                )
            )
            > 0
        )
        if not is_authorized:
            abort(403)

        return None, False
