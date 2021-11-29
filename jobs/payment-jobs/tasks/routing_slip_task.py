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
from typing import List

from flask import current_app
from pay_api import db
from pay_api.models import CfsAccount as CfsAccountModel
from pay_api.models import PaymentAccount as PaymentAccountModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.services.cfs_service import CFSService
from pay_api.utils.enums import CfsAccountStatus, RoutingSlipStatus
from sentry_sdk import capture_message
from sqlalchemy import and_
from sqlalchemy.orm import aliased


class RoutingSlipTask:  # pylint:disable=too-few-public-methods
    """Task to link routing slips."""

    @classmethod
    def link_routing_slips(cls):
        """Create invoice in CFS.

        Steps:
        1. Find all pending rs with pending status.
        1. Notify mailer
        """
        child = aliased(RoutingSlipModel)
        subquery = db.session.query(RoutingSlipModel.payment_account_id).filter(
            RoutingSlipModel.number == child.parent_number).subquery()
        routing_slips: List[RoutingSlipModel] = db.session.query(child).filter(and_(
            child.status == RoutingSlipStatus.LINKED.value, child.payment_account_id != subquery)).all()

        for routing_slip in routing_slips:

            #
            # 1.reverse the child routing slip
            # 2.create receipt to the parent
            # 3.change the payment account of child to parent
            # 4. change the status

            try:
                current_app.logger.debug(f'Reverse receipt {routing_slip.number}')
                payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(
                    routing_slip.payment_account_id)
                cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(
                    payment_account.id)

                # reverse routing slip receipt
                CFSService.reverse_rs_receipt_in_cfs(cfs_account, routing_slip.number)
                cfs_account.status = CfsAccountStatus.INACTIVE.value
                cfs_account.flush()

                # apply receipt to parent cfs account
                parent_rs = RoutingSlipModel.find_by_number(routing_slip.parent_number)
                parent_payment_account: PaymentAccountModel = PaymentAccountModel.find_by_id(
                    parent_rs.payment_account_id)

                parent_cfs_account: CfsAccountModel = CfsAccountModel.find_effective_by_account_id(
                    parent_payment_account.id)

                # For linked routing slip receipts, append 'L' to the number to avoid duplicate error
                receipt_number = f'{routing_slip.number}L'
                CFSService.create_cfs_receipt(cfs_account=parent_cfs_account,
                                              rcpt_number=receipt_number,
                                              rcpt_date=routing_slip.routing_slip_date.strftime('%Y-%m-%d'),
                                              amount=routing_slip.total,
                                              payment_method=parent_payment_account.payment_method)

                routing_slip.payment_account_id = parent_payment_account.id
                routing_slip.status = RoutingSlipStatus.LINKED.value
                routing_slip.save()

            except Exception as e:  # NOQA # pylint: disable=broad-except
                capture_message(
                    f'Error on Linking Routing Slip number:={routing_slip.number}, '
                    f'routing slip : {routing_slip.id}, ERROR : {str(e)}', level='error')
                current_app.logger.error(e)
                continue
