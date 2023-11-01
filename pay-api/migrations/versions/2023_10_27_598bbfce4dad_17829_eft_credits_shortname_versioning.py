"""17829-eft-credits-shortname-versioning

Revision ID: 598bbfce4dad
Revises: 194cdd7cf986
Create Date: 2023-10-27 12:11:36.931753

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '598bbfce4dad'
down_revision = '2ef58b39cafc'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('eft_credits',
                    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
                    sa.Column('amount', sa.Numeric(), nullable=False),
                    sa.Column('remaining_amount', sa.Numeric(), nullable=False),
                    sa.Column('payment_account_id', sa.Integer(), nullable=False),
                    sa.Column('eft_file_id', sa.Integer(), nullable=False),
                    sa.Column('created_on', sa.DateTime(), nullable=False),
                    sa.ForeignKeyConstraint(['payment_account_id'], ['payment_accounts.id'], ),
                    sa.ForeignKeyConstraint(['eft_file_id'], ['eft_files.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )

    op.create_table('eft_short_names_version',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('short_name', sa.String(), nullable=False),
                    sa.Column('auth_account_id', sa.String(length=50), nullable=True),
                    sa.Column('created_on', sa.DateTime(), nullable=False),
                    sa.Column('transaction_id', sa.BigInteger(), autoincrement=False, nullable=False),
                    sa.Column('end_transaction_id', sa.BigInteger(), nullable=True),
                    sa.Column('operation_type', sa.SmallInteger(), nullable=False),
                    sa.PrimaryKeyConstraint('id', 'transaction_id')
                    )


def downgrade():
    op.drop_table('eft_credits')
    op.drop_table('eft_short_names_version')
