"""Table to track EFT Short name historical payment activities.

Revision ID: e64c153e63ae
Revises: f9c15c7f29f5
Create Date: 2024-07-25 13:27:04.018005

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e64c153e63ae'
down_revision = '4e57f6cf649c'
branch_labels = None
depends_on = None


def upgrade():
    # EFT Credit Invoice Group Link sequence created outside for a table so the same value can be used for
    # multiple records
    op.execute(sa.schema.CreateSequence(sa.Sequence('eft_group_link_seq', data_type=sa.Integer)))

    with op.batch_alter_table('eft_credit_invoice_links', schema=None) as batch_op:
        batch_op.add_column(sa.Column('link_group_id', sa.Integer(), nullable=True))

    op.create_table('eft_short_names_historical',
                    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
                    sa.Column('amount', sa.Numeric(precision=19, scale=2), nullable=False),
                    sa.Column('created_by', sa.String(), nullable=True),
                    sa.Column('created_on', sa.DateTime(), nullable=False),
                    sa.Column('credit_balance', sa.Numeric(precision=19, scale=2), nullable=False),
                    sa.Column('description', sa.String(), nullable=False),
                    sa.Column('hidden', sa.Boolean(), nullable=False),
                    sa.Column('is_processing', sa.Boolean(), nullable=False),
                    sa.Column('payment_account_id', sa.Integer(), nullable=True),
                    sa.Column('related_group_link_id', sa.Integer(), nullable=True),
                    sa.Column('short_name_id', sa.Integer(), nullable=False),
                    sa.Column('statement_number', sa.Integer(), nullable=True),
                    sa.Column('transaction_date', sa.DateTime(), nullable=False),
                    sa.Column('transaction_type', sa.String(), nullable=False),
                    sa.ForeignKeyConstraint(['payment_account_id'], ['payment_accounts.id'], ),
                    sa.ForeignKeyConstraint(['short_name_id'], ['eft_short_names.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    with op.batch_alter_table('eft_short_names_historical', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_eft_short_names_historical_hidden'), ['hidden'], unique=False)
        batch_op.create_index(batch_op.f('ix_eft_short_names_historical_payment_account_id'), ['payment_account_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_eft_short_names_historical_related_group_link_id'), ['related_group_link_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_eft_short_names_historical_transaction_date'), ['transaction_date'], unique=False)

    with op.batch_alter_table('eft_credits', schema=None) as batch_op:
        batch_op.drop_index('ix_eft_credits_payment_account_id')
        batch_op.drop_constraint('eft_credits_payment_account_id_fkey', type_='foreignkey')
        batch_op.drop_column('payment_account_id')


def downgrade():
    with op.batch_alter_table('eft_short_names_historical', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_eft_short_names_historical_transaction_date'))
        batch_op.drop_index(batch_op.f('ix_eft_short_names_historical_related_group_link_id'))
        batch_op.drop_index(batch_op.f('ix_eft_short_names_historical_payment_account_id'))
        batch_op.drop_index(batch_op.f('ix_eft_short_names_historical_hidden'))

    op.drop_table('eft_short_names_historical')

    with op.batch_alter_table('eft_credit_invoice_links', schema=None) as batch_op:
        batch_op.alter_column('status_code',
                              existing_type=sa.VARCHAR(length=25),
                              nullable=True)
        batch_op.drop_column('link_group_id')

    op.execute('DROP SEQUENCE eft_group_link_seq')

    with op.batch_alter_table('eft_credits', schema=None) as batch_op:
        batch_op.add_column(sa.Column('payment_account_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.create_foreign_key('eft_credits_payment_account_id_fkey', 'payment_accounts', ['payment_account_id'], ['id'])
        batch_op.create_index('ix_eft_credits_payment_account_id', ['payment_account_id'], unique=False)
