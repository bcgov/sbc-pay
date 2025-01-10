"""23812 - update deposit and transaction dates to support timezones as it is reading from a TDI17

Revision ID: 3103082f36d5
Revises: 4f3a44eeade8
Create Date: 2025-01-10 07:41:35.755177

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '3103082f36d5'
down_revision = '88d31807423b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('eft_transactions', schema=None) as batch_op:
        batch_op.alter_column('deposit_date',
                              existing_type=postgresql.TIMESTAMP(),
                              type_=sa.DateTime(timezone=True),
                              existing_nullable=True)
        batch_op.alter_column('transaction_date',
                              existing_type=postgresql.TIMESTAMP(),
                              type_=sa.DateTime(timezone=True),
                              existing_nullable=True)

        # Update existing timezone data, existing data values are America/Vancouver but stored as UTC
        # Fixes data to be accurate for UTC (time updates)
        op.execute(text("""
            UPDATE eft_transactions
            SET deposit_date = (deposit_date AT TIME ZONE 'America/Vancouver') AT TIME ZONE 'UTC',
                transaction_date = (transaction_date AT TIME ZONE 'America/Vancouver') AT TIME ZONE 'UTC'
        """))


def downgrade():
    with op.batch_alter_table('eft_transactions', schema=None) as batch_op:
        batch_op.alter_column('transaction_date',
                              existing_type=sa.DateTime(timezone=True),
                              type_=postgresql.TIMESTAMP(),
                              existing_nullable=True)
        batch_op.alter_column('deposit_date',
                              existing_type=sa.DateTime(timezone=True),
                              type_=postgresql.TIMESTAMP(),
                              existing_nullable=True)
