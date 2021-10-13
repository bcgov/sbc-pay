"""fas rs refunds

Revision ID: 999f11310f30
Revises: f74980cff974
Create Date: 2021-10-13 14:32:38.882045

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = '999f11310f30'
down_revision = 'f74980cff974'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('refunds', sa.Column('routing_slip_id', sa.Integer(), nullable=True))
    op.add_column('refunds', sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.alter_column('refunds', 'invoice_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.create_foreign_key('refunds_rs_fk', 'refunds', 'routing_slips', ['routing_slip_id'], ['id'])
    op.create_check_constraint(
        'routing_slip_invoice_id_check',
        table_name='refunds',
        condition='NOT(routing_slip_id IS NULL AND invoice_id IS NULL)'
    )
    rs_status_table = table('routing_slip_status_codes',
                            column('code', sa.String),
                            column('description', sa.String),
                            )
    op.bulk_insert(
        rs_status_table,
        [
            {'code': 'REFUND_REQUESTED', 'description': 'Refund Requested'},
            {'code': 'REFUND_AUTHORIZED', 'description': 'Refund Authorised'},
            {'code': 'REFUND_COMPLETED', 'description': 'Refund Complete'}
        ]
    )


def downgrade():
    op.drop_constraint('routing_slip_invoice_id_check', 'refunds', type_='check')
    op.drop_constraint('refunds_rs_fk', 'refunds', type_='foreignkey')
    op.alter_column('refunds', 'invoice_id',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.drop_column('refunds', 'details')
    op.drop_column('refunds', 'routing_slip_id')
    op.execute("DELETE FROM routing_slip_status_codes where code in ('REFUND_REQUESTED',"
               "'REFUND_AUTHORIZED','REFUND_COMPLETED')")
