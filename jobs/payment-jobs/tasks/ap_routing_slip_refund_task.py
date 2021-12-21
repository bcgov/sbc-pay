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
"""Task to create AP file for FAS refunds."""

from typing import List

import time
from flask import current_app
from pay_api.models import EjvFile as EjvFileModel
from pay_api.models import EjvHeader as EjvHeaderModel
from pay_api.models import Refund as RefundModel
from pay_api.models import RoutingSlip as RoutingSlipModel
from pay_api.models import db
from pay_api.utils.enums import DisbursementStatus, EjvFileType, RoutingSlipStatus

from tasks.common.cgi_ap import CgiAP


class ApRoutingSlipRefundTask(CgiAP):
    """Task to create AP Files."""

    @classmethod
    def create_ap_file(cls):
        """Create AP files and uplaod to CGI.

        Steps:
        1. Find all routing slip with status REFUND_AUTHORIZED
        2. Create AP file and upload to SFTP
        """
        cls._create_routing_slip_refund_file()

    @classmethod
    def _create_routing_slip_refund_file(cls):  # pylint:disable=too-many-locals, too-many-statements
        """Create AP file for refund and upload."""
        # Find all routing slips with status REFUND_AUTHORIZED.
        routing_slips: List[RoutingSlipModel] = db.session.query(RoutingSlipModel) \
            .filter(RoutingSlipModel.status == RoutingSlipStatus.REFUND_AUTHORIZED.value)\
            .filter(RoutingSlipModel.refund_amount > 0)\
            .all()

        current_app.logger.info(f'Found {len(routing_slips)} to refund.')
        if not routing_slips:
            return

        # Create a file model record.
        ejv_file_model: EjvFileModel = EjvFileModel(
            file_type=EjvFileType.REFUND.value,
            file_ref=cls.get_file_name(),
            disbursement_status_code=DisbursementStatus.UPLOADED.value
        ).flush()

        batch_number = cls.get_batch_number(ejv_file_model.id)

        # JV Batch Header
        ap_content: str = cls.get_batch_header(batch_number)

        # Each routing slip will be one invoice in AP
        batch_total = 0
        for routing_slip in routing_slips:
            current_app.logger.info(f'Creating refund for {routing_slip.number}, Amount {routing_slip.refund_amount}.')
            refund: RefundModel = RefundModel.find_by_routing_slip_id(routing_slip.id)
            # Construct journal name
            EjvHeaderModel(
                disbursement_status_code=DisbursementStatus.UPLOADED.value,
                ejv_file_id=ejv_file_model.id
            ).flush()
            # AP Invoice Header
            ap_content = f'{ap_content}{cls.get_ap_header(routing_slip.refund_amount, routing_slip.number)}'
            ap_content = f'{ap_content}{cls.get_ap_invoice_line(routing_slip.refund_amount, routing_slip.number)}'
            ap_content = f'{ap_content}{cls.get_ap_address(refund.details, routing_slip.number)}'
            ap_content = f'{ap_content}{cls.get_ap_comment(refund.details, routing_slip.number)}'
            batch_total += routing_slip.refund_amount
            routing_slip.status = RoutingSlipStatus.REFUND_UPLOADED.value

        # AP Batch Trailer
        ap_content = f'{ap_content}{cls.get_batch_trailer(batch_number, batch_total, control_total=len(routing_slips))}'

        # Create a file add this content.
        file_path_with_name, trg_file_path = cls.create_inbox_and_trg_files(ap_content)

        # Upload file and trg to FTP
        cls.upload(ap_content, cls.get_file_name(), file_path_with_name, trg_file_path)

        # commit changes to DB
        db.session.commit()

        # Add a sleep to prevent collision on file name.
        time.sleep(1)
