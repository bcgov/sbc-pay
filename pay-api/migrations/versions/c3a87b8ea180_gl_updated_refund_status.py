"""Add in new invoice status for refunds.

Revision ID: c3a87b8ea180
Revises: 59fc9d74101f
Create Date: 2022-08-15 15:22:38.982600

"""
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = 'c3a87b8ea180'
down_revision = '59fc9d74101f'
branch_labels = None
depends_on = None

def upgrade():
    status_code_table = table('invoice_status_code',
                              column('code', String),
                              column('description', String)
                              )

    op.bulk_insert(
        status_code_table,
        [
            {'code': 'GL_UPDATED_REFUND', 'description': 'Revenue account updated - Refund'}
        ]
    )


def downgrade():
    op.execute('DELETE FROM invoice_status_code WHERE code = \'GL_UPDATED_REFUND\';')
