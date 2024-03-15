"""Migration for new history tables

Revision ID: fb3ba97b603a
Revises: bacb2b859d78
Create Date: 2024-03-15 15:22:53.140353

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'fb3ba97b603a'
down_revision = 'bacb2b859d78'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('eft_short_names_history',
    sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('auth_account_id', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('created_on', sa.DateTime(), autoincrement=False, nullable=False),
    sa.Column('short_name', sa.String(), autoincrement=False, nullable=False),
    sa.Column('linked_by', sa.String(length=100), autoincrement=False, nullable=True),
    sa.Column('linked_by_name', sa.String(length=100), autoincrement=False, nullable=True),
    sa.Column('linked_on', sa.DateTime(), autoincrement=False, nullable=True),
    sa.Column('version', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('changed', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id', 'version'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('eft_short_names_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_eft_short_names_history_auth_account_id'), ['auth_account_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_eft_short_names_history_short_name'), ['short_name'], unique=False)

    op.create_table('payment_accounts_history',
    sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('auth_account_id', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('name', sa.String(length=250), autoincrement=False, nullable=True),
    sa.Column('branch_name', sa.String(length=250), autoincrement=False, nullable=True),
    sa.Column('payment_method', sa.String(length=15), autoincrement=False, nullable=True),
    sa.Column('bcol_user_id', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('bcol_account', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('statement_notification_enabled', sa.Boolean(), autoincrement=False, nullable=True),
    sa.Column('credit', sa.Numeric(precision=19, scale=2), autoincrement=False, nullable=True),
    sa.Column('billable', sa.Boolean(), autoincrement=False, nullable=True),
    sa.Column('eft_enable', sa.Boolean(), autoincrement=False, nullable=False),
    sa.Column('pad_activation_date', sa.DateTime(), autoincrement=False, nullable=True),
    sa.Column('pad_tos_accepted_date', sa.DateTime(), autoincrement=False, nullable=True),
    sa.Column('pad_tos_accepted_by', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('version', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('changed', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['payment_method'], ['payment_methods.code'], ),
    sa.PrimaryKeyConstraint('id', 'version'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('payment_accounts_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payment_accounts_history_auth_account_id'), ['auth_account_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payment_accounts_history_bcol_account'), ['bcol_account'], unique=False)
        batch_op.create_index(batch_op.f('ix_payment_accounts_history_bcol_user_id'), ['bcol_user_id'], unique=False)

    op.create_table('account_fees_history',
    sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('account_id', sa.Integer(), autoincrement=False, nullable=True),
    sa.Column('apply_filing_fees', sa.Boolean(), autoincrement=False, nullable=True),
    sa.Column('service_fee_code', sa.String(length=10), autoincrement=False, nullable=True),
    sa.Column('product', sa.String(length=20), autoincrement=False, nullable=True),
    sa.Column('created_on', sa.DateTime(), autoincrement=False, nullable=False),
    sa.Column('updated_on', sa.DateTime(), autoincrement=False, nullable=True),
    sa.Column('created_by', sa.String(length=50), autoincrement=False, nullable=False),
    sa.Column('created_name', sa.String(length=100), autoincrement=False, nullable=True),
    sa.Column('updated_by', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('updated_name', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('version', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('changed', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['payment_accounts.id'], ),
    sa.ForeignKeyConstraint(['service_fee_code'], ['fee_codes.code'], ),
    sa.PrimaryKeyConstraint('id', 'version'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('account_fees_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_account_fees_history_account_id'), ['account_id'], unique=False)

    op.create_table('cfs_accounts_history',
    sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('cfs_account', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('cfs_party', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('cfs_site', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('payment_instrument_number', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('contact_party', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('bank_number', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('bank_branch_number', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('status', sa.String(length=40), autoincrement=False, nullable=True),
    sa.Column('account_id', sa.Integer(), autoincrement=False, nullable=True),
    sa.Column('bank_account_number', sqlalchemy_utils.types.encrypted.encrypted_type.StringEncryptedType(), autoincrement=False, nullable=True),
    sa.Column('version', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('changed', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['payment_accounts.id'], ),
    sa.ForeignKeyConstraint(['status'], ['cfs_account_status_codes.code'], ),
    sa.PrimaryKeyConstraint('id', 'version'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('cfs_accounts_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cfs_accounts_history_account_id'), ['account_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_cfs_accounts_history_bank_account_number'), ['bank_account_number'], unique=False)
        batch_op.create_index(batch_op.f('ix_cfs_accounts_history_bank_branch_number'), ['bank_branch_number'], unique=False)
        batch_op.create_index(batch_op.f('ix_cfs_accounts_history_bank_number'), ['bank_number'], unique=False)
        batch_op.create_index(batch_op.f('ix_cfs_accounts_history_cfs_account'), ['cfs_account'], unique=False)

    op.create_table('distribution_codes_history',
    sa.Column('distribution_code_id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('name', sa.String(length=250), autoincrement=False, nullable=True),
    sa.Column('client', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('responsibility_centre', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('service_line', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('stob', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('project_code', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('start_date', sa.Date(), autoincrement=False, nullable=False),
    sa.Column('end_date', sa.Date(), autoincrement=False, nullable=True),
    sa.Column('stop_ejv', sa.Boolean(), autoincrement=False, nullable=True),
    sa.Column('service_fee_distribution_code_id', sa.Integer(), autoincrement=False, nullable=True),
    sa.Column('disbursement_distribution_code_id', sa.Integer(), autoincrement=False, nullable=True),
    sa.Column('account_id', sa.Integer(), autoincrement=False, nullable=True),
    sa.Column('created_on', sa.DateTime(), autoincrement=False, nullable=False),
    sa.Column('updated_on', sa.DateTime(), autoincrement=False, nullable=True),
    sa.Column('created_by', sa.String(length=50), autoincrement=False, nullable=False),
    sa.Column('created_name', sa.String(length=100), autoincrement=False, nullable=True),
    sa.Column('updated_by', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('updated_name', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('version', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('changed', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['payment_accounts.id'], ),
    # sa.ForeignKeyConstraint(['disbursement_distribution_code_id'], ['distribution_codes_history.distribution_code_id'], ),
    # sa.ForeignKeyConstraint(['service_fee_distribution_code_id'], ['distribution_codes_history.distribution_code_id'], ),
    sa.PrimaryKeyConstraint('distribution_code_id', 'version'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('distribution_codes_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_distribution_codes_history_account_id'), ['account_id'], unique=False)

    op.create_table('refunds_partial_history',
    sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('payment_line_item_id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('refund_amount', sa.Numeric(precision=19, scale=2), autoincrement=False, nullable=False),
    sa.Column('refund_type', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('disbursement_status_code', sa.String(length=20), autoincrement=False, nullable=True),
    sa.Column('disbursement_date', sa.DateTime(), autoincrement=False, nullable=True),
    sa.Column('created_on', sa.DateTime(), autoincrement=False, nullable=False),
    sa.Column('updated_on', sa.DateTime(), autoincrement=False, nullable=True),
    sa.Column('created_by', sa.String(length=50), autoincrement=False, nullable=False),
    sa.Column('created_name', sa.String(length=100), autoincrement=False, nullable=True),
    sa.Column('updated_by', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('updated_name', sa.String(length=50), autoincrement=False, nullable=True),
    sa.Column('version', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('changed', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['disbursement_status_code'], ['disbursement_status_codes.code'], ),
    sa.ForeignKeyConstraint(['payment_line_item_id'], ['payment_line_items.id'], ),
    sa.PrimaryKeyConstraint('id', 'version'),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('refunds_partial_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_refunds_partial_history_payment_line_item_id'), ['payment_line_item_id'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('refunds_partial_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_refunds_partial_history_payment_line_item_id'))

    op.drop_table('refunds_partial_history')
    with op.batch_alter_table('distribution_codes_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_distribution_codes_history_account_id'))

    op.drop_table('distribution_codes_history')
    with op.batch_alter_table('cfs_accounts_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cfs_accounts_history_cfs_account'))
        batch_op.drop_index(batch_op.f('ix_cfs_accounts_history_bank_number'))
        batch_op.drop_index(batch_op.f('ix_cfs_accounts_history_bank_branch_number'))
        batch_op.drop_index(batch_op.f('ix_cfs_accounts_history_bank_account_number'))
        batch_op.drop_index(batch_op.f('ix_cfs_accounts_history_account_id'))

    op.drop_table('cfs_accounts_history')
    with op.batch_alter_table('account_fees_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_account_fees_history_account_id'))

    op.drop_table('account_fees_history')
    with op.batch_alter_table('payment_accounts_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payment_accounts_history_bcol_user_id'))
        batch_op.drop_index(batch_op.f('ix_payment_accounts_history_bcol_account'))
        batch_op.drop_index(batch_op.f('ix_payment_accounts_history_auth_account_id'))

    op.drop_table('payment_accounts_history')
    with op.batch_alter_table('eft_short_names_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_eft_short_names_history_short_name'))
        batch_op.drop_index(batch_op.f('ix_eft_short_names_history_auth_account_id'))

    op.drop_table('eft_short_names_history')
    # ### end Alembic commands ###
