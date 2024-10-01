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

from pay_api.models import db
from pay_api.models.eft_refund import EFTRefund as EFTRefundModel
from tests.utilities.base_test import factory_eft_shortname


def test_eft_refund_defaults(session):
    """Assert EFT refund defaults are stored."""
    # Ensure the required entry exists in the related table
    short_name = factory_eft_shortname(short_name='Test Short Name')
    db.session.add(short_name)
    db.session.commit()
    short_name_id = short_name.id

    eft_refund = EFTRefundModel(
        short_name_id=short_name_id,
        refund_amount=100.00,
        cas_supplier_number='SUP123456',
        refund_email='test@example.com',
        comment='Test comment'
    )
    eft_refund.save()

    # Retrieve and assert the EFT refund
    eft_refund = db.session.query(EFTRefundModel).filter(EFTRefundModel.id == eft_refund.id).one_or_none()

    assert eft_refund.id is not None
    assert eft_refund.created_on is not None
    assert eft_refund.updated_on is None
    assert eft_refund.short_name_id == short_name_id
    assert eft_refund.refund_amount == 100.00
    assert eft_refund.cas_supplier_number == 'SUP123456'
    assert eft_refund.refund_email == 'test@example.com'
    assert eft_refund.comment == 'Test comment'
    assert eft_refund.status is None
    assert eft_refund.updated_by is None
    assert eft_refund.updated_name is None


def test_eft_refund_all_attributes(session):
    """Assert all EFT refund attributes are stored."""
    # Ensure the required entry exists in the related table
    short_name = factory_eft_shortname(short_name='Test Short Name').save()
    refund_amount = 150.00
    cas_supplier_number = 'SUP654321'
    refund_email = 'updated@example.com'
    comment = 'Updated comment'
    status = 'COMPLETED'
    created_by = 'user111'
    decline_reason = 'Decline reason comment'
    updated_by = 'user123'
    updated_name = 'User Name'

    eft_refund = EFTRefundModel(
        short_name_id=short_name.id,
        refund_amount=refund_amount,
        cas_supplier_number=cas_supplier_number,
        refund_email=refund_email,
        comment=comment,
        decline_reason=decline_reason,
        status=status,
        created_by=created_by,
        updated_by=updated_by,
        updated_name=updated_name,
    )
    eft_refund.save()

    eft_refund = db.session.query(EFTRefundModel).filter(EFTRefundModel.id == eft_refund.id).one_or_none()

    assert eft_refund is not None
    assert eft_refund.short_name_id == short_name.id
    assert eft_refund.refund_amount == refund_amount
    assert eft_refund.cas_supplier_number == cas_supplier_number
    assert eft_refund.refund_email == refund_email
    assert eft_refund.comment == comment
    assert eft_refund.decline_reason == decline_reason
    assert eft_refund.status == status
    assert eft_refund.created_by == created_by
    assert eft_refund.updated_by == updated_by
    assert eft_refund.updated_name == updated_name
