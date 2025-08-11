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
"""Service to manage routing slip operations."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Set

from flask import abort, current_app

from pay_api.exceptions import BusinessException
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import Comment as CommentModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import RoutingSlipSchema
from pay_api.services.fas.routing_slip_status_transition_service import RoutingSlipStatusTransitionService
from pay_api.services.oauth_service import OAuthService
from pay_api.utils.enums import (
    AuthHeaderType,
    CfsAccountStatus,
    ContentType,
    PatchActions,
    PaymentMethod,
    PaymentStatus,
    PaymentSystem,
    Role,
    RoutingSlipStatus,
)
from pay_api.utils.errors import Error
from pay_api.utils.user_context import UserContext, user_context
from pay_api.utils.util import get_local_time, get_quantized, string_to_date


class RoutingSlip:
    """Service to manage Routing slip related operations."""

    @classmethod
    def asdict(cls, dao) -> Dict[str]:
        """Return the routing slip as a python dict."""
        routing_slip_schema = RoutingSlipSchema()
        d = routing_slip_schema.dump(dao)
        return d

    @classmethod
    def search(cls, search_filter: Dict, page: int, limit: int, return_all: bool = False):
        """Search for routing slip."""
        routing_slips, total = RoutingSlipModel.search(search_filter, page, limit, return_all)
        data = {
            "total": total,
            "page": page,
            "limit": limit,
            # Future: Use CATTRS
            # We need these fields, to populate the UI.
            "items": RoutingSlipSchema(
                only=(
                    "number",
                    "payments.receipt_number",
                    "payment_account.name",
                    "created_name",
                    "routing_slip_date",
                    "status",
                    "refund_status",
                    "invoices.business_identifier",
                    "payments.cheque_receipt_number",
                    "remaining_amount",
                    "total",
                    "invoices.corp_type_code",
                    "payments.payment_method_code",
                    "payments.payment_status_code",
                    "payment_account.payment_method",
                )
            ).dump(routing_slips, many=True),
        }

        return data

    @classmethod
    @user_context
    def create_daily_reports(cls, date: str, **kwargs):
        """Create and return daily report for the day provided."""
        routing_slips: List[RoutingSlipModel] = RoutingSlipModel.search(
            {
                "dateFilter": {
                    "endDate": date,
                    "startDate": date,
                    "target": "created_on",
                },
                "excludeStatuses": [RoutingSlipStatus.VOID.value],
            },
            page=1,
            limit=0,
            return_all=True,
        )[0]

        total: float = 0
        no_of_cash: int = 0
        no_of_cheque: int = 0
        total_cash_usd = 0
        total_cheque_usd = 0
        total_cash_cad = 0
        total_cheque_cad = 0
        for routing_slip in routing_slips:
            total += float(routing_slip.total)
            if routing_slip.payment_account.payment_method == PaymentMethod.CASH.value:
                no_of_cash += 1
                total_cash_cad += routing_slip.total
                if routing_slip.total_usd is not None:
                    total_cash_usd += routing_slip.total_usd
            else:
                no_of_cheque += len(routing_slip.payments)
                total_cheque_cad += routing_slip.total
                if routing_slip.total_usd is not None:
                    total_cheque_usd += routing_slip.total_usd

        # Future: Use CATTRS
        report_dict = {
            "templateName": "routing_slip_report",
            "reportName": f"Routing-Slip-Daily-Report-{date}",
            "templateVars": {
                "day": date,
                "reportDay": str(get_local_time(datetime.now(tz=timezone.utc))),
                "total": float(total),
                "numberOfCashReceipts": no_of_cash,
                "numberOfChequeReceipts": no_of_cheque,
                "totalCashInUsd": float(total_cash_usd),
                "totalChequeInUsd": float(total_cheque_usd),
                "totalCashInCad": float(total_cash_cad),
                "totalChequeInCad": float(total_cheque_cad),
            },
        }

        pdf_response = OAuthService.post(
            current_app.config.get("REPORT_API_BASE_URL"),
            kwargs["user"].bearer_token,
            AuthHeaderType.BEARER,
            ContentType.JSON,
            report_dict,
        )

        return pdf_response, report_dict.get("reportName")

    @classmethod
    def validate_and_find_by_number(cls, rs_number: str) -> Dict[str, any]:
        """Validate digits before finding by routing slip number."""
        if not current_app.config.get("ALLOW_LEGACY_ROUTING_SLIPS"):
            RoutingSlip._validate_routing_slip_number_digits(rs_number)
        return cls.find_by_number(rs_number)

    @classmethod
    def find_by_number(cls, rs_number: str) -> Dict[str, any]:
        """Find by routing slip number."""
        routing_slip_dict: Dict[str, any] = None
        if routing_slip := RoutingSlipModel.find_by_number(rs_number):
            # Future: Use CATTRS
            routing_slip_schema = RoutingSlipSchema(
                exclude=(
                    "city",
                    "country",
                    "delivery_instructions",
                    "postal_code",
                    "region",
                    "street",
                    "street_additional",
                )
            )
            routing_slip_dict = routing_slip_schema.dump(routing_slip)
            routing_slip_dict["allowedStatuses"] = RoutingSlipStatusTransitionService.get_possible_transitions(
                routing_slip
            )
            # Future: Use CATTRS
            routing_slip_dict["mailingAddress"] = {
                "city": routing_slip.city,
                "country": routing_slip.country,
                "deliveryInstructions": routing_slip.delivery_instructions,
                "postalCode": routing_slip.postal_code,
                "region": routing_slip.region,
                "street": routing_slip.street,
                "streetAdditional": routing_slip.street_additional,
            }

        return routing_slip_dict

    @classmethod
    def get_links(cls, rs_number: str) -> Dict[str, any]:
        """Find dependents/links of a routing slips."""
        links: Dict[str, any] = None
        if routing_slip := RoutingSlipModel.find_by_number(rs_number):
            routing_slip_schema = RoutingSlipSchema()
            children = RoutingSlipModel.find_children(rs_number)
            links = {
                "parent": routing_slip_schema.dump(routing_slip.parent),
                "children": routing_slip_schema.dump(children, many=True),
            }

        return links

    @classmethod
    @user_context
    def create(cls, request_json: Dict[str, any], **kwargs):
        """Search for routing slip."""
        # 1. Create customer profile in CFS and store it in payment_account and cfs_accounts
        # 2. Create receipt in CFS
        # 3. Create routing slip and payment records.

        rs_number = request_json.get("number")
        # Validate Routing slip digits and if slip number is unique.
        if cls.validate_and_find_by_number(rs_number):
            raise BusinessException(Error.FAS_INVALID_ROUTING_SLIP_NUMBER)

        payment_methods: List[str] = [payment.get("paymentMethod") for payment in request_json.get("payments")]
        # all the payment should have the same payment method
        if len(set(payment_methods)) != 1:
            raise BusinessException(Error.FAS_INVALID_PAYMENT_METHOD)

        # If payment method is cheque and then there is no payment date then raise error
        if payment_methods[0] == PaymentMethod.CHEQUE.value:
            for payment in request_json.get("payments"):
                if payment.get("paymentDate") is None:
                    raise BusinessException(Error.INVALID_REQUEST)

        pay_account = PaymentAccountModel(
            name=request_json.get("paymentAccount").get("accountName"),
            payment_method=payment_methods[0],
        ).flush()

        CfsAccountModel(
            account_id=pay_account.id,
            payment_method=PaymentMethod.INTERNAL.value,
            status=CfsAccountStatus.PENDING.value,
        ).flush()

        total = get_quantized(sum(float(payment.get("paidAmount")) for payment in request_json.get("payments")))

        # Calculate Total USD
        total_usd = get_quantized(
            sum(float(payment.get("paidUsdAmount", 0)) for payment in request_json.get("payments"))
        )

        mailing_address = request_json.get("mailingAddress", {})
        # Create a routing slip record.
        routing_slip = RoutingSlipModel(
            number=rs_number,
            payment_account_id=pay_account.id,
            status=RoutingSlipStatus.ACTIVE.value,
            total=total,
            remaining_amount=total,
            routing_slip_date=string_to_date(request_json.get("routingSlipDate")),
            total_usd=total_usd,
            contact_name=request_json.get("contactName"),
            street=mailing_address.get("street", ""),
            street_additional=mailing_address.get("streetAdditional", ""),
            city=mailing_address.get("city", ""),
            region=mailing_address.get("region", ""),
            postal_code=mailing_address.get("postalCode", ""),
            country=mailing_address.get("country", ""),
            delivery_instructions=mailing_address.get("deliveryInstructions", ""),
        ).flush()

        for payment in request_json.get("payments"):
            PaymentModel(
                payment_system_code=PaymentSystem.FAS.value,
                payment_account_id=pay_account.id,
                payment_method_code=payment.get("paymentMethod"),
                payment_status_code=PaymentStatus.COMPLETED.value,
                receipt_number=rs_number,
                cheque_receipt_number=payment.get("chequeReceiptNumber"),
                is_routing_slip=True,
                paid_amount=payment.get("paidAmount"),
                payment_date=string_to_date(payment.get("paymentDate")),
                created_by=kwargs["user"].user_name,
                paid_usd_amount=payment.get("paidUsdAmount", None),
            ).flush()

        routing_slip.commit()
        return cls.find_by_number(rs_number)

    @classmethod
    def do_link(cls, rs_number: str, parent_rs_number: str) -> Dict[str, any]:
        """Link routing slip to parent routing slip."""
        routing_slip = RoutingSlipModel.find_by_number(rs_number)
        parent_routing_slip = RoutingSlipModel.find_by_number(parent_rs_number)
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
    @user_context
    def update(cls, rs_number: str, action: str, request_json: Dict[str, any], **kwargs) -> Dict[str, any]:
        """Update routing slip."""
        user: UserContext = kwargs["user"]
        if (patch_action := PatchActions.from_value(action)) is None:
            raise BusinessException(Error.PATCH_INVALID_ACTION)

        if (routing_slip := RoutingSlipModel.find_by_number(rs_number)) is None:
            raise BusinessException(Error.FAS_INVALID_ROUTING_SLIP_NUMBER)

        if patch_action == PatchActions.UPDATE_REFUND_STATUS:
            refund_status = request_json.get("refund_status")
            routing_slip.refund_status = refund_status

        if patch_action == PatchActions.UPDATE_STATUS:
            status = request_json.get("status")
            RoutingSlipStatusTransitionService.validate_possible_transitions(routing_slip, status)
            status = RoutingSlipStatusTransitionService.get_actual_status(status)

            RoutingSlip._check_roles_for_status_update(status, user)
            # Our routing_slips job will create an invoice (under transactions in the UI).
            if status == RoutingSlipStatus.NSF.value:
                # Update the remaining amount as negative total of sum of all totals for that routing slip.
                total_paid_to_reverse: float = 0
                for rs in (
                    routing_slip,
                    *RoutingSlipModel.find_children(routing_slip.number),
                ):
                    total_paid_to_reverse += rs.total
                routing_slip.remaining_amount += -total_paid_to_reverse
            elif status == RoutingSlipStatus.VOID.value:
                if routing_slip.invoices:
                    raise BusinessException(Error.RS_HAS_TRANSACTIONS)
                routing_slip.remaining_amount = 0
            # This is outside the normal flow of payments, thus why we've done it here in FAS.
            elif status == RoutingSlipStatus.CORRECTION.value:
                if not request_json.get("payments"):
                    raise BusinessException(Error.INVALID_REQUEST)
                correction_total, comment = cls._calculate_correction_and_comment(rs_number, request_json)
                routing_slip.total += correction_total
                routing_slip.remaining_amount += correction_total
                CommentModel(comment=comment, routing_slip_number=rs_number).flush()
                # Set the routing slip status back to ACTIVE or COMPLETE, if it isn't created in CFS yet.
                cfs_account = CfsAccountModel.find_effective_by_payment_method(
                    routing_slip.payment_account_id, PaymentMethod.INTERNAL.value
                )
                if cfs_account and cfs_account.status == CfsAccountStatus.PENDING.value or not cfs_account:
                    status = (
                        RoutingSlipStatus.COMPLETE.value
                        if routing_slip.remaining_amount == 0
                        else RoutingSlipStatus.ACTIVE.value
                    )

            routing_slip.status = status

        routing_slip.save()
        return cls.find_by_number(rs_number)

    @classmethod
    def _calculate_correction_and_comment(cls, rs_number: str, request_json: Dict[str, any]):
        correction_total = Decimal("0")
        comment: str = ""
        payments = PaymentModel.find_payments_for_routing_slip(rs_number)
        for payment_request in request_json.get("payments"):
            if payment := next(x for x in payments if x.id == payment_request.get("id")):
                paid_amount = Decimal(str(payment_request.get("paidAmount", 0)))
                correction_total += paid_amount - payment.paid_amount
                if payment.payment_method_code == PaymentMethod.CASH.value:
                    comment += f"Cash Payment corrected amount" f" from ${payment.paid_amount} to ${paid_amount}\n"
                else:
                    comment += f"Cheque Payment {payment.cheque_receipt_number}"
                    if cheque_receipt_number := payment_request.get("chequeReceiptNumber"):
                        payment.cheque_receipt_number = cheque_receipt_number
                        comment += f", cheque receipt number corrected to {cheque_receipt_number}"
                    if paid_amount != payment.paid_amount:
                        comment += f", corrected amount from ${payment.paid_amount} to ${paid_amount}"
                    comment += ". \n"
                payment.paid_amount = paid_amount
                payment.paid_usd_amount = payment_request.get("paidUsdAmount", 0)
                payment.flush()
        return correction_total, comment

    @staticmethod
    def _check_roles_for_status_update(status: str, user: UserContext):
        """Check roles for the status."""
        if status == RoutingSlipStatus.VOID.value and not user.has_role(Role.FAS_VOID.value):
            abort(403)
        if status == RoutingSlipStatus.CORRECTION.value and not user.has_role(Role.FAS_CORRECTION.value):
            abort(403)
        if status in (
            RoutingSlipStatus.WRITE_OFF_AUTHORIZED.value,
            RoutingSlipStatus.REFUND_AUTHORIZED.value,
        ) and not user.has_role(Role.FAS_REFUND_APPROVER.value):
            abort(403)

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

        # Stop the user from linking NSF. NSF can only be a parent.
        if routing_slip.status == RoutingSlipStatus.NSF.value:
            raise BusinessException(Error.RS_CANT_LINK_NSF)

        RoutingSlip._validate_status(parent_rs_slip, routing_slip)

    @staticmethod
    def _is_linked_already(routing_slip: RoutingSlipModel):
        """Find if the rs is already linked."""
        return routing_slip.parent or routing_slip.status == RoutingSlipStatus.LINKED.value

    @staticmethod
    def _validate_status(routing_slip: RoutingSlipModel, child_rs: RoutingSlipModel):
        """Check if status belongs to any of these.These are invalid status for linking."""
        rs_statuses: Set[str] = {routing_slip.status, child_rs.status}
        invalid_statuses: Set[str] = {
            RoutingSlipStatus.REFUND_REQUESTED.value,
            RoutingSlipStatus.REFUND_AUTHORIZED.value,
            RoutingSlipStatus.REFUND_PROCESSED.value,
            RoutingSlipStatus.WRITE_OFF_REQUESTED.value,
            RoutingSlipStatus.WRITE_OFF_AUTHORIZED.value,
            RoutingSlipStatus.WRITE_OFF_COMPLETED.value,
            RoutingSlipStatus.COMPLETE.value,
            RoutingSlipStatus.VOID.value,
            RoutingSlipStatus.CORRECTION.value,
        }
        if rs_statuses.intersection(invalid_statuses):
            raise BusinessException(Error.RS_IN_INVALID_STATUS)

    @staticmethod
    def _validate_routing_slip_number_digits(rs_number: str):
        if len(rs_number) != 9 or not rs_number.isdigit():
            raise BusinessException(Error.FAS_INVALID_ROUTING_SLIP_DIGITS)

        # Using the first 8 digits of the routing slip
        data_digits = list(map(int, rs_number[:8]))
        validation_digit = int(rs_number[8])
        # For every 2nd digit:
        # -- Multiply the digit by 2
        # -- If the sum is 2 digits, add the two digits together (this will always be a 1 digit number in this case)
        replacement_digits = [
            int(str(x)[0]) + int(str(x)[1]) if x > 9 else x for x in [i * 2 for i in data_digits[1::2]]
        ]
        # -- Substitute the resulting digit for the original digit in the iteration
        replacement_digits.reverse()
        data_digits[1::2] = replacement_digits[: len(data_digits[1::2])]
        # Add all numbers together (of the 8 digits)
        # Subtract the 2nd digit of the sum from 10
        checksum = (10 - (sum(data_digits) % 10)) % 10
        # The difference should equal the 9th digit of the routing slip ID
        if validation_digit != checksum:
            raise BusinessException(Error.FAS_INVALID_ROUTING_SLIP_DIGITS)
