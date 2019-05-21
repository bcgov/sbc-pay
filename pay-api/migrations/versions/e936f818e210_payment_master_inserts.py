"""payment_master_inserts

Revision ID: e936f818e210
Revises: a377560a51ab
Create Date: 2019-05-21 13:06:56.599945

"""

from alembic import op
from sqlalchemy import Date, Integer, String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = 'e936f818e210'
down_revision = 'a377560a51ab'
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
            {'code': 'CREATE', 'description': 'Created'},
            {'code': 'COMPLETE', 'description': 'Completed'},
            {'code': 'PARTIAL', 'description': 'Partial'},
            {'code': 'FAIL', 'description': 'Failed'},
            {'code': 'REFUND', 'description': 'Refunded'}
        ]
    )


def downgrade():
    pass
