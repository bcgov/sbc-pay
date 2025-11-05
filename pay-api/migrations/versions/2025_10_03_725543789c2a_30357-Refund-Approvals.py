"""30357 Refund Approval flow updates

Revision ID: 725543789c2a
Revises: b313916b778a
Create Date: 2025-10-03 06:11:33.519859

"""
from alembic import op
import sqlalchemy as sa

from pay_api.utils.enums import RefundStatus, RefundType

revision = '725543789c2a'
down_revision = 'c1e2b8b9384f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('corp_types', schema=None) as batch_op:
        batch_op.add_column(sa.Column('refund_approval', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))

    with op.batch_alter_table('refunds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('decline_reason', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('notification_email', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('refund_method', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('staff_comment', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=25), nullable=True))
        batch_op.add_column(sa.Column('type', sa.String(length=25), nullable=True))
        batch_op.create_index(batch_op.f('ix_refunds_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_refunds_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_refunds_type'), ['type'], unique=False)

    # Update all previous refunds that did not use the approval flow
    op.execute(f"UPDATE refunds SET status='{RefundStatus.APPROVAL_NOT_REQUIRED.value}' WHERE status IS NULL")

    # Update refund type for routing slip refunds
    op.execute(f"UPDATE refunds SET type='{RefundType.ROUTING_SLIP.value}' WHERE routing_slip_id is not null")

    # Update refund type for invoices
    op.execute(f"UPDATE refunds SET type='{RefundType.INVOICE.value}' WHERE routing_slip_id is null")

    # Fix full refund validation - should not allow CC it will error as we don't support the credits, but it could cause
    # a credit memo to be created in error
    op.execute(f"UPDATE payment_methods SET full_refund_statuses=null where code='CC'")

    with op.batch_alter_table('refunds', schema=None) as batch_op:
        batch_op.alter_column('status', nullable=False)
        batch_op.alter_column('type', nullable=False)

    with op.batch_alter_table('refunds_partial', schema=None) as batch_op:
        batch_op.add_column(sa.Column('refund_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('refunds_partial_refund_id_fkey', 'refunds', ['refund_id'], ['id'])

    with op.batch_alter_table('refunds_partial_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('refund_id', sa.Integer(), autoincrement=False, nullable=True))

    # Update refund id based on existing refund records
    op.execute(
        """
        UPDATE refunds_partial
        SET refund_id = (
            SELECT id FROM refunds
            WHERE refunds.invoice_id = refunds_partial.invoice_id
            ORDER BY id ASC
            LIMIT 1
            )
        WHERE EXISTS (
            SELECT 1 FROM refunds
            WHERE refunds.invoice_id = refunds_partial.invoice_id
            )
        """
    )

    op.execute(
        """
        UPDATE refunds_partial_history
        SET refund_id = (
            SELECT id FROM refunds
            WHERE refunds.invoice_id = refunds_partial_history.invoice_id
            ORDER BY id ASC
            LIMIT 1
            )
        WHERE EXISTS (
            SELECT 1 FROM refunds
            WHERE refunds.invoice_id = refunds_partial_history.invoice_id
            )
        """
    )


def downgrade():
    with op.batch_alter_table('refunds', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_refunds_id'))
        batch_op.drop_index(batch_op.f('ix_refunds_type'))
        batch_op.drop_index(batch_op.f('ix_refunds_status'))
        batch_op.drop_column('decline_reason')
        batch_op.drop_column('refund_method')
        batch_op.drop_column('status')
        batch_op.drop_column('staff_comment')
        batch_op.drop_column('type')
        batch_op.drop_column('notification_email')

    with op.batch_alter_table('corp_types', schema=None) as batch_op:
        batch_op.drop_column('refund_approval')

    with op.batch_alter_table('refunds_partial', schema=None) as batch_op:
        batch_op.drop_constraint('refunds_partial_refund_id_fkey', type_='foreignkey')
        batch_op.alter_column('invoice_id',
                              existing_type=sa.INTEGER(),
                              nullable=False)
        batch_op.drop_column('refund_id')

    with op.batch_alter_table('refunds_partial_history', schema=None) as batch_op:
        batch_op.drop_column('refund_id')
