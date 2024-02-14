"""empty message

Revision ID: ec34224aaf53
Revises: bbd1189e4e75
Create Date: 2024-02-09 15:34:10.429544

"""
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = 'ec34224aaf53'
down_revision = 'bbd1189e4e75'
branch_labels = None
depends_on = None


def upgrade():
    status_code_table = table('invoice_status_codes',
                            column('code', String),
                            column('description', String)
                            )
    op.bulk_insert(
        status_code_table,
        [
            {'code': 'PARTIAL_REFUNDED', 'description': 'Partial Refunded'}
        ]
    )

def downgrade():
    op.execute("delete from invoice_status_codes where code in ('PARTIAL_REFUNDED')")
 