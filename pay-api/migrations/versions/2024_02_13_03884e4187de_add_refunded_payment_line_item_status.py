"""empty message

Revision ID: 03884e4187de
Revises: ec34224aaf53
Create Date: 2024-02-13 16:20:27.695392

"""
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = '03884e4187de'
down_revision = 'ec34224aaf53'
branch_labels = None
depends_on = None


def upgrade():
    status_code_table = table('line_item_status_codes',
                            column('code', String),
                            column('description', String)
                            )
    op.bulk_insert(
        status_code_table,
        [
            {'code': 'REFUNDED', 'description': 'Refunded'},
            {'code': 'REFUND_REQUESTED', 'description': 'Refund Requested'},
            {'code': 'SETTLEMENT_SCHED', 'description': 'Settlement Scheduled'},
            {'code': 'REFUND_AUTHORIZED', 'description': 'Refund Authorised'},
            {'code': 'REFUND_COMPLETED', 'description': 'Refund Complete'}
        ]
    )


def downgrade():
    op.execute("delete from line_item_status_codes where code in ('REFUNDED', 'REFUND_REQUESTED', 'SETTLEMENT_SCHED', 'REFUND_AUTHORIZED', 'REFUND_COMPLETED')")
