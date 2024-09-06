"""add primary key constraint to eft_refund_email_list table

Revision ID: f9c15c7f29f5
Revises: fb59bf68146d
Create Date: 2024-07-22 14:52:01.050844

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import Sequence, CreateSequence

# revision identifiers, used by Alembic.
revision = 'f9c15c7f29f5'
down_revision = 'fb59bf68146d'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('eft_refund_email_list')

    op.execute(CreateSequence(Sequence('eft_refund_email_list_id_seq')))

    op.create_table('eft_refund_email_list',
        sa.Column('id', sa.Integer(), 
                  sa.Sequence('eft_refund_email_list_id_seq'), 
                  server_default=sa.text("nextval('eft_refund_email_list_id_seq'::regclass)"),
                  nullable=False),
        sa.Column('first_name', sa.String(25), nullable=True),
        sa.Column('last_name', sa.String(25), nullable=True),
        sa.Column('email', sa.String(25), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
def downgrade():
    op.drop_table('eft_refund_email_list')

    op.execute('DROP SEQUENCE eft_refund_email_list_id_seq')

    op.create_table('eft_refund_email_list',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('first_name', sa.String(25), nullable=True),
        sa.Column('last_name', sa.String(25), nullable=True),
        sa.Column('email', sa.String(25), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
