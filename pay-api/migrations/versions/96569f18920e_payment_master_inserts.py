"""payment_master_inserts

Revision ID: 96569f18920e
Revises: 0d50feb5a623
Create Date: 2019-05-16 15:24:20.085282

"""
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = '96569f18920e'
down_revision = '0d50feb5a623'
branch_labels = None
depends_on = None


def upgrade():
    payment_method_table = table('payment_method',
                                 column('code', String),
                                 column('description', String)
                                 )
    payment_system_table = table('payment_system',
                                 column('code', String),
                                 column('description', String)
                                 )
    status_code_table = table('status_code',
                              column('code', String),
                              column('description', String)
                              )

    op.bulk_insert(
        payment_method_table,
        [
            {'code': 'CC', 'description': 'Credit Card'}
        ]
    )
    op.bulk_insert(
        payment_system_table,
        [
            {'code': 'PAYBC', 'description': 'Pay BC System'}
        ]
    )
    op.bulk_insert(
        status_code_table,
        [
            {'code': 'DRAFT', 'description': 'Draft'},
            {'code': 'IN_PROGRESS', 'description': 'In Progress'},
            {'code': 'COMPLETE', 'description': 'Completed'},
            {'code': 'PARTIAL', 'description': 'Partial'},
            {'code': 'FAIL', 'description': 'Failed'},
            {'code': 'REFUND', 'description': 'Refunded'}
        ]
    )


def downgrade():
    pass
