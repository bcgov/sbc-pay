# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests to assure the EFT Refund model.

Test-Suite to ensure that the EFT Refund model is working as expected.
"""
from datetime import datetime, timezone

from pay_api.models import db
from pay_api.models.eft_refund import EFTRefund as EFTRefundModel


def test_eft_refund_defaults(session):
    """Assert EFT refund defaults are stored."""
    eft_refund = EFTRefundModel()
    eft_refund.short_name_id = 1
    eft_refund.refund_amount = 100.00
    eft_refund.cas_supplier_number = 'SUP123456'
    eft_refund.refund_email = 'test@example.com'
    eft_refund.comment = 'Test comment'
    eft_refund.save()

    eft_refund = db.session.query(EFTRefundModel).filter(EFTRefundModel.id == eft_refund.id).one_or_none()

    assert eft_refund.id is not None
    assert eft_refund.created_on is not None
    assert eft_refund.updated_on is None
    assert eft_refund.short_name_id == 1
    assert eft_refund.refund_amount == 100.00
    assert eft_refund.cas_supplier_number == 'SUP123456'
    assert eft_refund.refund_email == 'test@example.com'
    assert eft_refund.comment == 'Test comment'
    assert eft_refund.status is None
    assert eft_refund.updated_by is None
    assert eft_refund.updated_by_name is None


def test_eft_refund_all_attributes(session):
    """Assert all EFT refund attributes are stored."""
    created_on = datetime.now(timezone.utc)
    updated_on = datetime.now(timezone.utc)
    refund_amount = 150.00
    cas_supplier_number = 'SUP654321'
    refund_email = 'updated@example.com'
    comment = 'Updated comment'
    status = 'COMPLETED'
    updated_by = 'user123'
    updated_by_name = 'User Name'

    eft_refund = EFTRefundModel()
    eft_refund.short_name_id = 1
    eft_refund.refund_amount = refund_amount
    eft_refund.cas_supplier_number = cas_supplier_number
    eft_refund.created_on = created_on
    eft_refund.refund_email = refund_email
    eft_refund.comment = comment
    eft_refund.status = status
    eft_refund.updated_by = updated_by
    eft_refund.updated_by_name = updated_by_name
    eft_refund.updated_on = updated_on
    eft_refund.save()

    eft_refund = eft_refund.find_by_id(eft_refund.id)

    assert eft_refund is not None
    assert eft_refund.created_on == created_on
    assert eft_refund.updated_on == updated_on
    assert eft_refund.short_name_id == 1
    assert eft_refund.refund_amount == refund_amount
    assert eft_refund.cas_supplier_number == cas_supplier_number
    assert eft_refund.refund_email == refund_email
    assert eft_refund.comment == comment
    assert eft_refund.status == status
    assert eft_refund.updated_by == updated_by
    assert eft_refund.updated_by_name == updated_by_name
