"""26465 - EFT Refund data fix for existing refunds

Revision ID: f6e2fd9710b7
Revises: 48f199450139
Create Date: 2025-03-17 10:09:39.847650

"""
from alembic import op
import sqlalchemy as sa

from pay_api.utils.enums import APRefundMethod

revision = 'f6e2fd9710b7'
down_revision = '48f199450139'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        f"update eft_refunds set refund_method='{APRefundMethod.EFT.value}' where refund_method is null"
    )


def downgrade():
    op.execute(
        f"update eft_refunds set refund_method=null where refund_method='{APRefundMethod.EFT.value}'"
    )
