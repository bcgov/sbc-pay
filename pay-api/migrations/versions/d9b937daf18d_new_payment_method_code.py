"""new payment method code

Revision ID: d9b937daf18d
Revises: 9543cbcb8b79
Create Date: 2021-09-07 07:43:38.067973

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = 'd9b937daf18d'
down_revision = '9543cbcb8b79'
branch_labels = None
depends_on = None


def upgrade():
    payment_method_table = table('payment_methods',
                                 column('code', String),
                                 column('description', String)
                                 )

    op.bulk_insert(
        payment_method_table,
        [
            {'code': 'ROUTING_SLIP', 'description': 'Routing Slip payment'},
        ]
    )


def downgrade():
    pass
