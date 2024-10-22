"""Refund Partial updates for automated refund job.

Revision ID: 59db97e9432e
Revises: ed487561aeeb
Create Date: 2024-10-21 10:18:58.828246

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '59db97e9432e'
down_revision = 'ed487561aeeb'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('refunds_partial', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gl_posted', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('invoice_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('refunds_partial_invoice_id_fkey', 'invoices', ['invoice_id'], ['id'])

    with op.batch_alter_table('refunds_partial_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gl_posted', sa.DateTime(), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('invoice_id', sa.Integer(), autoincrement=False, nullable=True))
        batch_op.create_foreign_key('refunds_partial_history_invoice_id_fkey', 'invoices', ['invoice_id'], ['id'])

    op.execute("""
    UPDATE refunds_partial
    SET invoice_id = (
        SELECT payment_line_items.invoice_id
        FROM payment_line_items
        WHERE payment_line_items.id = refunds_partial.payment_line_item_id
    )
    """)

    op.execute("""
    UPDATE refunds_partial_history
    SET invoice_id = (
        SELECT payment_line_items.invoice_id
        FROM payment_line_items
        WHERE payment_line_items.id = refunds_partial_history.payment_line_item_id
    )
    """)

    with op.batch_alter_table('refunds_partial', schema=None) as batch_op:
        batch_op.alter_column('invoice_id', nullable=False)

    with op.batch_alter_table('refunds_partial_history', schema=None) as batch_op:
        batch_op.alter_column('invoice_id', nullable=False)


def downgrade():
    with op.batch_alter_table('refunds_partial_history', schema=None) as batch_op:
        batch_op.drop_constraint('refunds_partial_history_invoice_id_fkey', type_='foreignkey')
        batch_op.drop_column('invoice_id')
        batch_op.drop_column('gl_posted')

    with op.batch_alter_table('refunds_partial', schema=None) as batch_op:
        batch_op.drop_constraint('refunds_partial_invoice_id_fkey', type_='foreignkey')
        batch_op.drop_column('invoice_id')
        batch_op.drop_column('gl_posted')
