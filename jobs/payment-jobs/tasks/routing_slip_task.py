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
"""Task to for linking routing slips."""

from datetime import UTC, datetime
from decimal import Decimal

from flask import current_app
from sqlalchemy import func

from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import DistributionCode as DistributionCodeModel
from pay_api.models import FeeSchedule as FeeScheduleModel
from pay_api.models import Invoice as InvoiceModel
from pay_api.models import InvoiceReference as InvoiceReferenceModel
from pay_api.models import Payment as PaymentModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import PaymentLineItem as PaymentLineItemModel
from pay_api.models import Receipt as ReceiptModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import db
from pay_api.services.cfs_service import CFSService
from pay_api.services.email_service import JobFailureNotification
from pay_api.utils.enums import (
    CfsAccountStatus,
    CfsReceiptStatus,
    InvoiceReferenceStatus,
    InvoiceStatus,
    LineItemStatus,
    PaymentMethod,
    PaymentStatus,
    PaymentSystem,
    ReverseOperation,
    RoutingSlipStatus,
)


class RoutingSlipTask:  # pylint:disable=too-few-public-methods
    """Task to link routing slips."""

    @classmethod
    def link_routing_slips(cls):
        """Create invoice in CFS.

        Steps:
        1. Find all pending rs with pending status.
        2. Notify mailer
        """
        routing_slips = cls._get_routing_slip_by_status(RoutingSlipStatus.LINKED.value)
        failures = []
        for routing_slip in routing_slips:
            # 1. Reverse the child routing slip.
            # 2. Create receipt to the parent.
            # 3. Change the payment account of child to parent.
            # 4. Change the status.
            cfs_account = None
            parent_rs = None
            parent_rs_remaining_after_sync_link = None
            try:
                current_app.logger.debug(f"Linking Routing Slip: {routing_slip.number}")
                payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(routing_slip.payment_account_id)
                cfs_account = CfsAccountModel.find_effective_by_payment_method(
                    payment_account.id, PaymentMethod.INTERNAL.value
                )

                # reverse routing slip receipt
                if CFSService.get_receipt(cfs_account, routing_slip.number).get("status") != CfsReceiptStatus.REV.value:
                    CFSService.reverse_rs_receipt_in_cfs(cfs_account, routing_slip.number, ReverseOperation.LINK.value)
                cfs_account.status = CfsAccountStatus.INACTIVE.value

                # apply receipt to parent cfs account
                parent_rs = RoutingSlipModel.find_by_number(routing_slip.parent_number)
                parent_rs_remaining_after_sync_link = parent_rs.remaining_amount
                parent_payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(
                    parent_rs.payment_account_id
                )
                parent_cfs_account = CfsAccountModel.find_effective_by_payment_method(
                    parent_payment_account.id, PaymentMethod.INTERNAL.value
                )
                # For linked routing slip receipts, append 'L' to the number to avoid duplicate error
                receipt_number = routing_slip.generate_cas_receipt_number()
                CFSService.create_cfs_receipt(
                    cfs_account=parent_cfs_account,
                    rcpt_number=receipt_number,
                    rcpt_date=routing_slip.routing_slip_date.strftime("%Y-%m-%d"),
                    amount=routing_slip.total,
                    payment_method=parent_payment_account.payment_method,
                    access_token=CFSService.get_token(PaymentSystem.FAS).json().get("access_token"),
                )

                # Add to the list if parent is NSF, to apply the receipts.
                if parent_rs.status == RoutingSlipStatus.NSF.value:
                    total_invoice_amount = cls._apply_routing_slips_to_pending_invoices(parent_rs)
                    current_app.logger.debug(f"Total Invoice Amount : {total_invoice_amount}")
                    # Update the parent routing slip status to ACTIVE
                    parent_rs.status = RoutingSlipStatus.ACTIVE.value
                    # linking routing slip balance is transferred ,so use the total
                    parent_rs.remaining_amount = routing_slip.total - total_invoice_amount

                routing_slip.save()

            except Exception as e:  # NOQA # pylint: disable=broad-except
                # Discard any uncommitted dirty state from this iteration (e.g. cfs_account.status)
                # before touching anything - otherwise it can get swept into a later, unrelated commit.
                db.session.rollback()
                current_app.logger.error(
                    f"Error on Linking Routing Slip number:={routing_slip.number}, "
                    f"routing slip : {routing_slip.id}, ERROR : {str(e)}",
                    exc_info=True,
                )
                rollback_ok = cls._rollback_failed_link(routing_slip, parent_rs, parent_rs_remaining_after_sync_link)
                failures.append((routing_slip.number, cls._failure_message(e, rollback_ok)))
                continue

        cls._notify_job_failures(
            failures,
            subject="Routing Slip Linking Job Failure",
            file_name="routing_slip_linking",
            job_name="Link Routing Slips Job",
        )

    @classmethod
    def process_correction(cls):
        """Process CORRECTION routing slips.

        Steps:
        1. Reverse the routing slip.
        2. Recreate the routing slip receipt with the corrected amount.
        3. Reset the invoices.
        4. Reapply the invoices.

        """
        routing_slips = cls._get_routing_slip_by_status(RoutingSlipStatus.CORRECTION.value)
        current_app.logger.info(f"Found {len(routing_slips)} to process CORRECTIONS.")
        failures = []
        for rs in routing_slips:
            cas_version_suffix_snapshot = rs.cas_version_suffix
            try:
                wait_for_create_invoice_job = any(
                    x.invoice_status_code in [InvoiceStatus.APPROVED.value, InvoiceStatus.CREATED.value]
                    for x in rs.invoices
                )
                if wait_for_create_invoice_job:
                    continue
                current_app.logger.debug(f"Correcting Routing Slip: {rs.number}")
                payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(rs.payment_account_id)
                cfs_account = CfsAccountModel.find_effective_by_payment_method(
                    payment_account.id, PaymentMethod.INTERNAL.value
                )

                # Skip if a previous, partially-failed attempt already reversed this receipt in CAS -
                # reversing an already-reversed receipt is not guaranteed to be safe to retry.
                if (
                    CFSService.get_receipt(cfs_account, rs.generate_cas_receipt_number()).get("status")
                    != CfsReceiptStatus.REV.value
                ):
                    CFSService.reverse_rs_receipt_in_cfs(
                        cfs_account,
                        rs.generate_cas_receipt_number(),
                        ReverseOperation.CORRECTION.value,
                    )
                # Update the version, which generates a new receipt number. This is to avoid duplicate receipt number.
                rs.cas_version_suffix += 1
                # Recreate the receipt with the modified total.
                CFSService.create_cfs_receipt(
                    cfs_account=cfs_account,
                    rcpt_number=rs.generate_cas_receipt_number(),
                    rcpt_date=rs.routing_slip_date.strftime("%Y-%m-%d"),
                    amount=rs.total,
                    payment_method=payment_account.payment_method,
                    access_token=CFSService.get_token(PaymentSystem.FAS).json().get("access_token"),
                )

                cls._reset_invoices_and_references_to_created(rs)

                cls._apply_routing_slips_to_pending_invoices(rs)

                rs.status = (
                    RoutingSlipStatus.COMPLETE.value if rs.remaining_amount == 0 else RoutingSlipStatus.ACTIVE.value
                )

                rs.save()
            except Exception as e:  # NOQA # pylint: disable=broad-except
                db.session.rollback()
                current_app.logger.error(
                    f"Error on Processing CORRECTION for :={rs.number}, routing slip : {rs.id}, ERROR : {str(e)}",
                    exc_info=True,
                )
                # Note: this only undoes the cas_version_suffix bump. If the original CAS receipt was
                # already reversed before the failure, that reversal itself can't be undone from here -
                # it needs the same manual recovery as any other CAS-side failure.
                rollback_ok = True
                try:
                    rs.cas_version_suffix = cas_version_suffix_snapshot
                    rs.save()
                except Exception as rollback_error:  # NOQA # pylint: disable=broad-except
                    rollback_ok = False
                    current_app.logger.error(
                        f"Rollback failed for Routing Slip number:={rs.number}, ERROR : {str(rollback_error)}",
                        exc_info=True,
                    )
                failures.append((rs.number, cls._failure_message(e, rollback_ok)))
                continue

        cls._notify_job_failures(
            failures,
            subject="Routing Slip Correction Job Failure",
            file_name="routing_slip_correction",
            job_name="Routing Slip Correction Job",
        )

    @classmethod
    def process_void(cls):
        """Process VOID routing slips.

        Steps:
        1. Reverse the routing slip receipt.
        2. Reverse all the child receipts.
        3. Change the CFS Account status.
        4. Adjust the remaining amount and cas_version_suffix for VOID.
        """
        routing_slips = cls._get_routing_slip_by_status(RoutingSlipStatus.VOID.value)
        current_app.logger.info(f"Found {len(routing_slips)} to process VOID.")
        failures = []
        for routing_slip in routing_slips:
            cfs_account = None
            child_routing_slips: list[RoutingSlipModel] = []
            reversed_numbers: list[str] = []
            remaining_amount_snapshot = routing_slip.remaining_amount
            cas_version_suffix_snapshot = routing_slip.cas_version_suffix
            try:
                current_app.logger.debug(f"Reverse receipt {routing_slip.number}")
                if routing_slip.invoices:
                    # FUTURE: If this is hit, and needs to change, we can do something similar to NSF.
                    # EX. Reset the invoices to created, invoice reference to active.
                    raise Exception("VOID - has transactions/invoices.")  # pylint: disable=broad-exception-raised

                payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(routing_slip.payment_account_id)
                cfs_account = CfsAccountModel.find_effective_by_payment_method(
                    payment_account.id, PaymentMethod.INTERNAL.value
                )

                # Reverse all child routing slips, as all linked routing slips are also considered as VOID.
                child_routing_slips = RoutingSlipModel.find_children(routing_slip.number)
                for rs in (routing_slip, *child_routing_slips):
                    receipt_number = rs.generate_cas_receipt_number()
                    CFSService.reverse_rs_receipt_in_cfs(cfs_account, receipt_number, ReverseOperation.VOID.value)
                    # Track this so a failure partway through the group can report exactly which
                    # members already had their CAS receipt reversed - those can't be re-reversed.
                    reversed_numbers.append(rs.number)
                # Void routing slips aren't supposed to have pending transactions, so no need to look at invoices.
                cfs_account.status = CfsAccountStatus.INACTIVE.value
                routing_slip.remaining_amount = 0
                # Increasing the version, incase we need to reuse the routing slip number in CAS.
                routing_slip.cas_version_suffix += 1
                routing_slip.save()
            except Exception as e:  # NOQA # pylint: disable=broad-except
                db.session.rollback()
                current_app.logger.error(
                    f"Error on Processing VOID for :={routing_slip.number}, "
                    f"routing slip : {routing_slip.id}, ERROR : {str(e)}",
                    exc_info=True,
                )
                # Note: this only undoes our own DB-side changes for this attempt. Any receipt that
                # was already reversed in CAS before the failure can't be undone from here - it needs
                # the same manual recovery as any other CAS-side failure.
                rollback_ok = True
                try:
                    if cfs_account is not None:
                        cfs_account.status = CfsAccountStatus.ACTIVE.value
                    routing_slip.remaining_amount = remaining_amount_snapshot
                    routing_slip.cas_version_suffix = cas_version_suffix_snapshot
                    routing_slip.save()
                except Exception as rollback_error:  # NOQA # pylint: disable=broad-except
                    rollback_ok = False
                    current_app.logger.error(
                        f"Rollback failed for Routing Slip number:={routing_slip.number}, ERROR : {str(rollback_error)}",
                        exc_info=True,
                    )
                all_numbers = [routing_slip.number] + [rs.number for rs in child_routing_slips]
                not_yet_reversed = [number for number in all_numbers if number not in reversed_numbers]
                partial_state_note = (
                    f"Already reversed in CAS: {reversed_numbers or 'none'}; not yet reversed: {not_yet_reversed}."
                )
                message = f"{cls._failure_message(e, rollback_ok)} {partial_state_note}"
                failures.append((routing_slip.number, message))
                continue

        cls._notify_job_failures(
            failures,
            subject="Routing Slip Void Job Failure",
            file_name="routing_slip_void",
            job_name="Routing Slip Void Job",
        )

    @classmethod
    def process_nsf(cls):
        """Process NSF routing slips.

        Steps:
        1. Find all routing slips with NSF status.
        2. Reverse the receipt for the NSF routing slips.
        3. Add an invoice for NSF fees.
        """
        routing_slips = cls._get_routing_slip_by_status(RoutingSlipStatus.NSF.value)
        current_app.logger.info(f"Found {len(routing_slips)} to process NSF.")
        for routing_slip in routing_slips:
            # 1. Reverse the routing slip receipt.
            # 2. Reverse all the child receipts.
            # 3. Change the CFS Account status to FREEZE.
            try:
                current_app.logger.debug(f"Reverse receipt {routing_slip.number}")
                payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(routing_slip.payment_account_id)
                cfs_account = CfsAccountModel.find_effective_by_payment_method(
                    payment_account.id, PaymentMethod.INTERNAL.value
                )

                # Find all child routing slip and reverse it, as all linked routing slips are also considered as NSF.
                child_routing_slips: list[RoutingSlipModel] = RoutingSlipModel.find_children(routing_slip.number)
                for rs in (routing_slip, *child_routing_slips):
                    receipt_number = rs.generate_cas_receipt_number()
                    CFSService.reverse_rs_receipt_in_cfs(cfs_account, receipt_number, ReverseOperation.NSF.value)

                    for payment in (
                        db.session.query(PaymentModel).filter(PaymentModel.receipt_number == receipt_number).all()
                    ):
                        payment.payment_status_code = PaymentStatus.FAILED.value

                cfs_account.status = CfsAccountStatus.FREEZE.value

                cls._reset_invoices_and_references_to_created(routing_slip)

                inv = cls._create_nsf_invoice(cfs_account, routing_slip.number, payment_account)
                # Reduce the NSF fee from remaining amount.
                routing_slip.remaining_amount = routing_slip.remaining_amount - inv.total
                routing_slip.save()

            except Exception as e:  # NOQA # pylint: disable=broad-except
                current_app.logger.error(
                    f"Error on Processing NSF for :={routing_slip.number}, "
                    f"routing slip : {routing_slip.id}, ERROR : {str(e)}",
                    exc_info=True,
                )
                continue

    @classmethod
    def adjust_routing_slips(cls):
        """Adjust routing slips.

        Steps:
        1. Validate adjustment amounts before adjusting.
        2. Check data consistency between SBC-PAY and CFS.
        3. Adjust routing slip receipts for Write off or Refund authorized.
        """
        current_app.logger.info("<<adjust_routing_slips")
        adjust_statuses = [
            RoutingSlipStatus.REFUND_AUTHORIZED.value,
            RoutingSlipStatus.WRITE_OFF_AUTHORIZED.value,
        ]
        # For any pending refund/write off balance should be more than $0
        routing_slips = (
            db.session.query(RoutingSlipModel)
            .filter(
                RoutingSlipModel.status.in_(adjust_statuses),
                RoutingSlipModel.remaining_amount > 0,
                RoutingSlipModel.cas_mismatch.is_not(True),
            )
            .all()
        )
        current_app.logger.info(f"Found {len(routing_slips)} to write off or refund authorized.")
        for routing_slip in routing_slips:
            try:
                child_routing_slips: list[RoutingSlipModel] = RoutingSlipModel.find_children(routing_slip.number)

                has_pending, pending_count = cls._has_pending_invoices(routing_slip, child_routing_slips)
                if has_pending:
                    current_app.logger.warning(
                        f"Skipping routing slip {routing_slip.number} - has {pending_count} pending invoices "
                        f"that need to be processed first"
                    )
                    continue

                # 1.Adjust the routing slip and it's child routing slips for the remaining balance.
                current_app.logger.debug(f"Adjusting routing slip {routing_slip.number}")
                payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(routing_slip.payment_account_id)
                cfs_account = CfsAccountModel.find_effective_by_payment_method(
                    payment_account.id, PaymentMethod.INTERNAL.value
                )

                # may raise ValueError
                cls._validate_and_calculate_adjustment_amount(routing_slip, cfs_account, child_routing_slips)

                # reverse routing slip receipt
                for rs in (routing_slip, *child_routing_slips):
                    is_refund = routing_slip.status == RoutingSlipStatus.REFUND_AUTHORIZED.value
                    receipt_number = rs.generate_cas_receipt_number()
                    # Adjust the receipt to zero in CFS
                    CFSService.adjust_receipt_to_zero(cfs_account, receipt_number, is_refund)

                routing_slip.refund_amount = routing_slip.remaining_amount
                routing_slip.remaining_amount = 0
                routing_slip.save()

            except ValueError as e:
                routing_slip.cas_mismatch = True
                routing_slip.save()
                current_app.logger.error(f"Skipping adjustment for routing slip {routing_slip.number}: {str(e)}")
                continue

            except Exception as e:  # NOQA # pylint: disable=broad-except
                current_app.logger.error(
                    f"Error on Adjusting Routing Slip for :={routing_slip.number}, "
                    f"routing slip : {routing_slip.id}, ERROR : {str(e)}",
                    exc_info=True,
                )
                continue

    @classmethod
    def _has_pending_invoices(
        cls, routing_slip: RoutingSlipModel, child_routing_slips: list[RoutingSlipModel]
    ) -> tuple[bool, int]:
        """Check if routing slip or its children have pending invoices."""
        all_routing_slips = [routing_slip] + child_routing_slips
        all_routing_slip_numbers = [rs.number for rs in all_routing_slips]

        pending_invoice_count = (
            db.session.query(InvoiceModel)
            .filter(
                InvoiceModel.routing_slip.in_(all_routing_slip_numbers),
                InvoiceModel.invoice_status_code.in_([InvoiceStatus.APPROVED.value, InvoiceStatus.CREATED.value]),
            )
            .count()
        )

        return (pending_invoice_count > 0, pending_invoice_count)

    @classmethod
    def _rollback_failed_link(
        cls,
        routing_slip: RoutingSlipModel,
        parent_rs: RoutingSlipModel,
        parent_rs_remaining_after_sync_link: Decimal,
    ) -> bool:
        """Undo the do_link changes so a failed link doesn't leave a half-migrated routing slip.

        - db.session.rollback() (called by the caller before this) only undoes changes made during
          this job run. It can't touch routing_slip.status/parent_number or the parent's
          remaining_amount - those were already committed by the earlier, synchronous do_link API
          call, in a separate transaction - so this method reverses them explicitly.
        - Goes to HOLD, not ACTIVE: we can't tell from here whether the CAS receipt was already
          reversed before the failure. HOLD blocks any spend either way, so it's safe regardless.
          ACTIVE would be wrong if the receipt is gone and the balance isn't backed by anything in CAS.
        - cfs_account is left as-is for the same reason.
        - A person must check the real CAS receipt state for this routing slip before moving it back
          to ACTIVE.

        Returns False if the rollback itself failed - the caller should treat that as more urgent
        than a routine CAS failure, since the routing slip's state is then unknown, not just on HOLD.
        """
        try:
            if parent_rs is not None and parent_rs_remaining_after_sync_link is not None:
                parent_rs.remaining_amount = parent_rs_remaining_after_sync_link - routing_slip.total
                parent_rs.save()
            routing_slip.status = RoutingSlipStatus.HOLD.value
            routing_slip.parent_number = None
            routing_slip.remaining_amount = routing_slip.total
            routing_slip.save()
            return True
        except Exception as rollback_error:  # NOQA # pylint: disable=broad-except
            current_app.logger.error(
                f"Rollback failed for Routing Slip number:={routing_slip.number}, ERROR : {str(rollback_error)}",
                exc_info=True,
            )
            return False

    @staticmethod
    def _failure_message(error: Exception, rollback_ok: bool) -> str:
        """Build the failure message, flagging when the rollback itself failed as more urgent."""
        if rollback_ok:
            return str(error)
        return f"URGENT - rollback also failed, routing slip state is unknown. Original error: {error}"

    @classmethod
    def _notify_job_failures(cls, failures: list[tuple[str, str]], subject: str, file_name: str, job_name: str) -> None:
        """Send a single summary notification for all routing slips that failed in this job run."""
        if not failures:
            return
        action_message = (
            "Action needed: verify the real CAS receipt state for each routing slip below before "
            "assuming its recorded balance is safe to use - do not rely on PAYDB's numbers alone."
        )
        notification = JobFailureNotification(
            subject=subject,
            file_name=file_name,
            error_messages=[
                {"error": action_message},
                *({"error": f"{number}: {error}"} for number, error in failures),
            ],
            table_name="routing_slips",
            job_name=job_name,
        )
        notification.send_notification()

    @classmethod
    def _get_routing_slip_by_status(cls, status: RoutingSlipStatus) -> list[RoutingSlipModel]:
        """Get routing slip by status."""
        return (
            db.session.query(RoutingSlipModel)
            .join(
                PaymentAccountModel,
                PaymentAccountModel.id == RoutingSlipModel.payment_account_id,
            )
            .join(CfsAccountModel, CfsAccountModel.account_id == PaymentAccountModel.id)
            .filter(RoutingSlipModel.status == status)
            .filter(CfsAccountModel.payment_method == PaymentMethod.INTERNAL.value)
            .filter(CfsAccountModel.status == CfsAccountStatus.ACTIVE.value)
            .all()
        )

    @classmethod
    def _get_applied_invoices_amount(cls, routing_slips: list[RoutingSlipModel]) -> Decimal:
        """Get total amount of applied invoices in SBC-PAY for routing slips."""
        routing_slip_numbers = [rs.number for rs in routing_slips]
        total_applied = (
            db.session.query(func.sum(InvoiceModel.paid - func.coalesce(InvoiceModel.refund, 0)))
            .filter(
                InvoiceModel.routing_slip.in_(routing_slip_numbers),
                InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value,
            )
            .scalar()
        )
        return total_applied or Decimal("0.0")

    @classmethod
    def _check_data_consistency(
        cls, routing_slip: RoutingSlipModel, sbc_pay_applied_amount: Decimal, cfs_receipt_details: list[dict]
    ) -> None:
        """Check data consistency between SBC-PAY and CFS."""
        sbc_pay_has_invoices = sbc_pay_applied_amount > 0
        cfs_has_invoices = any(receipt["has_applied_invoices"] for receipt in cfs_receipt_details)

        if sbc_pay_has_invoices != cfs_has_invoices:
            error_msg = (
                f"Data mismatch for routing slip {routing_slip.number}: "
                f"SBC-PAY applied amount: ${sbc_pay_applied_amount:.2f}, "
                f"CFS has applied invoices: {cfs_has_invoices}. "
                f"Manual intervention required."
            )
            if not current_app.config.get("DISABLE_RS_ADJUSTMENT_ERROR_EMAIL"):
                notification = JobFailureNotification(
                    subject="Routing Slip Adjustment Job Failure",
                    file_name="routing_slip_adjustment",
                    error_messages=[{"error": error_msg}],
                    table_name="routing_slips",
                    job_name="Routing Slip Adjustment Job",
                )
                notification.send_notification()
            raise ValueError(error_msg)

    @classmethod
    def _validate_and_calculate_adjustment_amount(
        cls, routing_slip: RoutingSlipModel, cfs_account: CfsAccountModel, child_routing_slips: list[RoutingSlipModel]
    ) -> None:
        """Validate adjustment amount for routing slip."""
        all_routing_slips = [routing_slip] + child_routing_slips

        sbc_pay_applied = cls._get_applied_invoices_amount(all_routing_slips)

        receipt_details = []
        cfs_unapplied_total = Decimal("0.0")

        for rs in all_routing_slips:
            receipt_number = rs.generate_cas_receipt_number()
            receipt_data = CFSService.get_receipt(cfs_account, receipt_number)
            unapplied_amount = Decimal(str(receipt_data.get("unapplied_amount", 0)))
            has_applied_invoices = len(receipt_data.get("invoices", [])) > 0
            receipt_details.append({"has_applied_invoices": has_applied_invoices})
            cfs_unapplied_total += unapplied_amount

        # may raise ValueError
        cls._check_data_consistency(routing_slip, sbc_pay_applied, receipt_details)
        all_rs_total = sum(rs.total for rs in all_routing_slips)
        expected_adjustment = all_rs_total - sbc_pay_applied

        amount_diff = abs(cfs_unapplied_total - expected_adjustment)
        if amount_diff > 0:
            error_msg = (
                f"Amount mismatch for routing slip {routing_slip.number}: "
                f"Expected adjustment ${expected_adjustment:.2f}, "
                f"but CFS unapplied amount is ${cfs_unapplied_total:.2f}. "
                f"Difference: ${amount_diff:.2f}"
            )
            raise ValueError(error_msg)

    @classmethod
    def _reset_invoices_and_references_to_created(cls, routing_slip: RoutingSlipModel):
        """Reset Invoices, Invoice references and Receipts for routing slip."""
        invoices: list[InvoiceModel] = (
            db.session.query(InvoiceModel)
            .filter(InvoiceModel.routing_slip == routing_slip.number)
            .filter(InvoiceModel.invoice_status_code == InvoiceStatus.PAID.value)
            .all()
        )
        for inv in invoices:
            # Reset the statuses
            inv.invoice_status_code = InvoiceStatus.CREATED.value
            inv_ref = InvoiceReferenceModel.find_by_invoice_id_and_status(
                inv.id, InvoiceReferenceStatus.COMPLETED.value
            )
            inv_ref.status_code = InvoiceReferenceStatus.ACTIVE.value
            # Delete receipts as receipts are reversed in CFS.
            for receipt in ReceiptModel.find_all_receipts_for_invoice(inv.id):
                db.session.delete(receipt)

    @classmethod
    def _create_nsf_invoice(
        cls,
        cfs_account: CfsAccountModel,
        rs_number: str,
        payment_account: PaymentAccountModel,
    ) -> InvoiceModel:
        """Create Invoice, line item and invoice reference records."""
        fee_schedule: FeeScheduleModel = FeeScheduleModel.find_by_filing_type_and_corp_type(
            corp_type_code="BCR", filing_type_code="NSF"
        )
        invoice = InvoiceModel(
            bcol_account=payment_account.bcol_account,
            payment_account_id=payment_account.id,
            cfs_account_id=cfs_account.id,
            invoice_status_code=InvoiceStatus.CREATED.value,
            total=fee_schedule.fee.amount,
            service_fees=0,
            paid=0,
            payment_method_code=PaymentMethod.INTERNAL.value,
            corp_type_code="BCR",
            created_on=datetime.now(tz=UTC),
            created_by="SYSTEM",
            routing_slip=rs_number,
        )
        invoice = invoice.save()
        distribution: DistributionCodeModel = DistributionCodeModel.find_by_active_for_fee_schedule(
            fee_schedule.fee_schedule_id
        )

        line_item = PaymentLineItemModel(
            invoice_id=invoice.id,
            total=invoice.total,
            fee_schedule_id=fee_schedule.fee_schedule_id,
            description=fee_schedule.filing_type.description,
            filing_fees=invoice.total,
            priority_fees=0,
            pst=0,
            future_effective_fees=0,
            line_item_status_code=LineItemStatus.ACTIVE.value,
            service_fees=0,
            fee_distribution_id=distribution.distribution_code_id,
        )
        line_item.save()

        invoice_response = CFSService.create_account_invoice(
            transaction_number=invoice.id,
            line_items=invoice.payment_line_items,
            cfs_account=cfs_account,
        )

        invoice_number = invoice_response.get("invoice_number", None)
        current_app.logger.info(f"invoice_number  {invoice_number}  created in CFS for NSF.")

        InvoiceReferenceModel(
            invoice_id=invoice.id,
            invoice_number=invoice_number,
            reference_number=invoice_response.get("pbc_ref_number", None),
            status_code=InvoiceReferenceStatus.ACTIVE.value,
        ).save()

        return invoice

    @classmethod
    def _apply_routing_slips_to_pending_invoices(cls, routing_slip: RoutingSlipModel) -> Decimal:
        """Apply the routing slips again."""
        current_app.logger.info(f"Applying routing slips to pending invoices for routing slip: {routing_slip.number}")
        routing_slip_payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(
            routing_slip.payment_account_id
        )

        # apply invoice to the active CFS_ACCOUNT which will be the parent routing slip
        active_cfs_account = CfsAccountModel.find_effective_by_payment_method(
            routing_slip_payment_account.id, PaymentMethod.INTERNAL.value
        )

        invoices: list[InvoiceModel] = (
            db.session.query(InvoiceModel)
            .filter(
                InvoiceModel.routing_slip == routing_slip.number,
                InvoiceModel.invoice_status_code.in_([InvoiceStatus.CREATED.value, InvoiceStatus.APPROVED.value]),
            )
            .all()
        )
        current_app.logger.info(f"Found {len(invoices)} to apply receipt")
        applied_amount = 0
        for inv in invoices:
            inv_ref: InvoiceReferenceModel = InvoiceReferenceModel.find_by_invoice_id_and_status(
                inv.id, InvoiceReferenceStatus.ACTIVE.value
            )
            cls.apply_routing_slips_to_invoice(
                routing_slip_payment_account,
                active_cfs_account,
                routing_slip,
                inv,
                inv_ref.invoice_number,
            )

            # IF invoice balance is zero, then update records.
            if (
                CFSService.get_invoice(cfs_account=active_cfs_account, inv_number=inv_ref.invoice_number).get(
                    "amount_due"
                )
                == 0
            ):
                applied_amount += inv.total
                inv_ref.status_code = InvoiceReferenceStatus.COMPLETED.value
                inv.invoice_status_code = InvoiceStatus.PAID.value
                inv.payment_date = datetime.now(tz=UTC)

        return applied_amount

    @classmethod
    def apply_routing_slips_to_invoice(  # pylint: disable = too-many-arguments, too-many-locals
        cls,
        routing_slip_payment_account: PaymentAccountModel,
        active_cfs_account: CfsAccountModel,
        parent_routing_slip: RoutingSlipModel,
        invoice: InvoiceModel,
        invoice_number: str,
    ) -> bool:
        """Apply routing slips (receipts in CFS) to invoice."""
        has_errors = False
        child_routing_slips: list[RoutingSlipModel] = RoutingSlipModel.find_children(parent_routing_slip.number)
        # an invoice has to be applied to multiple receipts (incl. all linked RS); apply till the balance is zero
        for routing_slip in (parent_routing_slip, *child_routing_slips):
            try:
                # apply receipt now
                receipt_number = routing_slip.generate_cas_receipt_number()
                current_app.logger.debug(
                    f"Apply receipt {receipt_number} on invoice {invoice_number} for routing slip {routing_slip.number}"
                )

                # If balance of receipt is zero, continue to next receipt.
                receipt_balance_before_apply = Decimal(
                    str(CFSService.get_receipt(active_cfs_account, receipt_number).get("unapplied_amount"))
                )
                current_app.logger.debug(f"Current balance on {receipt_number} = {receipt_balance_before_apply}")
                if receipt_balance_before_apply == 0:
                    continue

                current_app.logger.debug(f"Applying receipt {receipt_number} to {invoice_number}")
                receipt_response = CFSService.apply_receipt(active_cfs_account, receipt_number, invoice_number)

                receipt = ReceiptModel()
                receipt.receipt_number = receipt_response.json().get("receipt_number", None)
                receipt_amount = receipt_balance_before_apply - Decimal(
                    str(receipt_response.json().get("unapplied_amount"))
                )
                receipt.receipt_amount = receipt_amount
                receipt.invoice_id = invoice.id
                receipt.receipt_date = datetime.now(tz=UTC)
                receipt.flush()

                invoice_from_cfs = CFSService.get_invoice(active_cfs_account, invoice_number)
                if invoice_from_cfs.get("amount_due") == 0:
                    break

            except Exception as e:  # NOQA # pylint: disable=broad-except
                current_app.logger.error(
                    f"Error on creating Routing Slip invoice: account id={routing_slip_payment_account.id}, "
                    f"routing slip : {routing_slip.id}, ERROR : {str(e)}",
                    exc_info=True,
                )
                has_errors = True
                continue
        return has_errors
