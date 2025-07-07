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
"""Task to notify staff user for short name over payments."""
from datetime import datetime, timedelta, timezone
from typing import List

from flask import current_app
from pay_api.models import db
from pay_api.models.eft_credit import EFTCredit as EFTCreditModel
from pay_api.models.eft_short_name_links import EFTShortnameLinks as EFTShortnameLinkModel
from pay_api.models.eft_short_names import EFTShortnames as EFTShortnameModel
from pay_api.services.auth import get_emails_with_keycloak_role
from pay_api.services.email_service import send_email
from pay_api.utils.enums import EFTShortnameStatus, Role
from sqlalchemy import and_, func

from services.email_service import _render_eft_overpayment_template


class EFTOverpaymentNotificationTask:  # pylint: disable=too-few-public-methods
    """Task to notify staff qualified receivers.

    Notify staff qualified receiver there is a pending unsettled amount on a short name due to overpayment or an account
    has not been linked for thirty days.
    """

    date_override = None
    short_names: dict = {}

    @classmethod
    def _get_short_names_with_credits_remaining(cls):
        """Create base query for returning short names with any remaining credits by filter date."""
        query = (
            db.session.query(EFTShortnameModel)
            .distinct(EFTShortnameModel.id)
            .join(EFTCreditModel, EFTCreditModel.short_name_id == EFTShortnameModel.id)
            .filter(EFTCreditModel.remaining_amount > 0)
            .order_by(EFTShortnameModel.id, EFTCreditModel.created_on.asc())
        )
        return query

    @classmethod
    def _get_today_overpaid_linked_short_names(cls):
        """Get linked short names that have received a payment today and overpaid."""
        filter_date = cls.date_override if cls.date_override is not None else datetime.now(tz=timezone.utc).date()
        query = (
            cls._get_short_names_with_credits_remaining()
            .join(
                EFTShortnameLinkModel,
                and_(
                    EFTShortnameLinkModel.eft_short_name_id == EFTShortnameModel.id,
                    EFTShortnameLinkModel.status_code.in_(
                        [
                            EFTShortnameStatus.LINKED.value,
                            EFTShortnameStatus.PENDING.value,
                        ]
                    ),
                ),
            )
            .filter(func.date(EFTCreditModel.created_on) == filter_date)
        )
        return query.all()

    @classmethod
    def _get_unlinked_short_names_for_duration(cls, days_duration: int = 30):
        """Get short names that have been unlinked for a duration in days."""
        execution_date = cls.date_override if cls.date_override is not None else datetime.now(tz=timezone.utc).date()
        duration_date = execution_date - timedelta(days=days_duration)
        query = (
            cls._get_short_names_with_credits_remaining()
            .outerjoin(
                EFTShortnameLinkModel,
                and_(
                    EFTShortnameLinkModel.eft_short_name_id == EFTShortnameModel.id,
                    EFTShortnameLinkModel.status_code.in_(
                        [
                            EFTShortnameStatus.LINKED.value,
                            EFTShortnameStatus.PENDING.value,
                        ]
                    ),
                ),
            )
            .filter(EFTShortnameLinkModel.id.is_(None))
            .filter(func.date(EFTShortnameModel.created_on) == duration_date)
        )

        return query.all()

    @classmethod
    def _update_short_name_dict(cls, short_name_models: List[EFTShortnameModel]):
        for short_name in short_name_models:
            cls.short_names[short_name.id] = short_name.short_name

    @classmethod
    def process_overpayment_notification(cls, date_override=None):
        """Notify for over payments and short name unlinked for thirty days."""
        try:
            cls.short_names = {}
            if date_override:
                cls.date_override = datetime.strptime(date_override, "%Y-%m-%d") if date_override else None
                current_app.logger.info(f"Using date override : {date_override}")

            # Get short names that have EFT credit rows created based on current / override date indicating payment
            # was received and credits remaining indicate overpayment
            linked_short_names = cls._get_today_overpaid_linked_short_names()

            # Get short names that have credits remaining and have been unlinked for thirty days
            unlinked_short_names = cls._get_unlinked_short_names_for_duration()

            cls._update_short_name_dict(linked_short_names)
            cls._update_short_name_dict(unlinked_short_names)
            current_app.logger.info(f"Sending over payment notifications for {len(cls.short_names)} short names.")
            cls._send_notifications()
        except Exception:  # NOQA # pylint: disable=broad-except
            current_app.logger.error("Error on processing over payment notifications", exc_info=True)

    @classmethod
    def _send_notifications(cls):
        """Send over payment notification."""
        if not cls.short_names:
            return

        qualified_receiver_recipients = get_emails_with_keycloak_role(Role.EFT_REFUND.value)
        for short_name_id, name in cls.short_names.items():
            credit_balance = EFTCreditModel.get_eft_credit_balance(short_name_id)
            template_params = {
                "shortNameId": short_name_id,
                "shortName": name,
                "unsettledAmount": f"{credit_balance:,.2f}",
            }
            send_email(
                recipients=qualified_receiver_recipients,
                subject=f"Pending Unsettled Amount for Short Name {name}",
                body=_render_eft_overpayment_template(template_params),
            )
