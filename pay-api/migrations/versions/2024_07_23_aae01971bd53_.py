"""Add in has_partner_disbursements column to corp_types, easier for querying, also remove unused columns.
Also add in partner disbursements.

Revision ID: aae01971bd53
Revises: fb59bf68146d
Create Date: 2024-07-23 10:51:20.058891

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'aae01971bd53'
down_revision = 'f9c15c7f29f5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('corp_types', schema=None) as batch_op:
        batch_op.add_column(sa.Column('has_partner_disbursements', sa.Boolean(), nullable=True))
    
    with op.batch_alter_table('refunds_partial', schema=None) as batch_op:
        batch_op.drop_constraint('refunds_partial_disbursement_status_code_fkey', type_='foreignkey')
        batch_op.drop_column('disbursement_status_code')
        batch_op.drop_column('disbursement_date')

    with op.batch_alter_table('refunds_partial_history', schema=None) as batch_op:
        batch_op.drop_constraint('refunds_partial_history_disbursement_status_code_fkey', type_='foreignkey')
        batch_op.drop_column('disbursement_status_code')
        batch_op.drop_column('disbursement_date')

    op.create_table('partner_disbursements',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('amount', sa.Numeric(), nullable=False),
        sa.Column('created_on', sa.DateTime(), nullable=False),
        sa.Column('feedback_on', sa.DateTime(), nullable=True),
        sa.Column('partner_code', sa.String(length=50), nullable=False),
        sa.Column('processed_on', sa.DateTime(), nullable=True),
        sa.Column('is_reversal', sa.Boolean(), nullable=False),
        sa.Column('status_code', sa.String(length=25), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('target_type', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('partner_disbursements')

    with op.batch_alter_table('corp_types', schema=None) as batch_op:
        batch_op.drop_column('has_partner_disbursements')
    
    with op.batch_alter_table('refunds_partial', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disbursement_status_code', sa.String(length=20), nullable=True))    
        batch_op.add_column(sa.Column('disbursement_date', sa.Date(), nullable=True))
        batch_op.create_foreign_key(None, 'refunds_partial', 'disbursement_status_codes', ['disbursement_status_code'], ['code'])

    with op.batch_alter_table('refunds_partial_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disbursement_status_code', sa.String(length=20), nullable=True))    
        batch_op.add_column(sa.Column('disbursement_date', sa.Date(), nullable=True))
        batch_op.create_foreign_key(None, 'refunds_partial_history', 'disbursement_status_codes', ['disbursement_status_code'], ['code'])

    
