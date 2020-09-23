"""empty message

Revision ID: 56c5db141909
Revises: 8f550bdc9491
Create Date: 2020-09-14 17:04:29.195866

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '56c5db141909'
down_revision = '8f550bdc9491'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('cfs_account',
                    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
                    sa.Column('cfs_account', sa.String(length=50), nullable=True),
                    sa.Column('cfs_party', sa.String(length=50), nullable=True),
                    sa.Column('cfs_site', sa.String(length=50), nullable=True),
                    sa.Column('bank_name', sa.String(length=50), nullable=True),
                    sa.Column('bank_number', sa.String(length=50), nullable=True),
                    sa.Column('bank_branch', sa.String(length=50), nullable=True),
                    sa.Column('bank_branch_number', sa.String(length=50), nullable=True),
                    sa.Column('bank_account_number', sa.String(length=50), nullable=True),
                    sa.Column('is_active', sa.Boolean(), nullable=True),
                    sa.Column('account_id', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['account_id'], ['payment_account.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_index(op.f('ix_cfs_account_account_id'), 'cfs_account', ['account_id'], unique=False)
    op.create_index(op.f('ix_cfs_account_bank_account_number'), 'cfs_account', ['bank_account_number'], unique=False)
    op.create_index(op.f('ix_cfs_account_bank_branch'), 'cfs_account', ['bank_branch'], unique=False)
    op.create_index(op.f('ix_cfs_account_bank_branch_number'), 'cfs_account', ['bank_branch_number'], unique=False)
    op.create_index(op.f('ix_cfs_account_bank_name'), 'cfs_account', ['bank_name'], unique=False)
    op.create_index(op.f('ix_cfs_account_bank_number'), 'cfs_account', ['bank_number'], unique=False)
    op.create_index(op.f('ix_cfs_account_cfs_account'), 'cfs_account', ['cfs_account'], unique=False)

    # op.drop_index('ix_internal_payment_account_account_id', table_name='internal_payment_account')
    # op.drop_table('internal_payment_account')
    # op.drop_index('ix_credit_payment_account_account_id', table_name='credit_payment_account')
    # op.drop_index('ix_credit_payment_account_paybc_account', table_name='credit_payment_account')
    # op.drop_table('credit_payment_account')
    # op.drop_index('ix_bcol_payment_account_account_id', table_name='bcol_payment_account')
    # op.drop_index('ix_bcol_payment_account_bcol_account_id', table_name='bcol_payment_account')
    # op.drop_index('ix_bcol_payment_account_bcol_user_id', table_name='bcol_payment_account')
    # op.drop_table('bcol_payment_account')
    op.add_column('invoice', sa.Column('bcol_account', sa.String(length=50), nullable=True))
    op.add_column('invoice', sa.Column('payment_account_id', sa.Integer(), nullable=True))

    op.add_column('payment_account', sa.Column('bcol_account', sa.String(length=50), nullable=True))
    op.add_column('payment_account', sa.Column('bcol_user_id', sa.String(length=50), nullable=True))
    op.add_column('payment_account', sa.Column('payment_method', sa.String(length=10), nullable=True))
    op.create_index(op.f('ix_payment_account_bcol_account'), 'payment_account', ['bcol_account'], unique=False)
    op.create_index(op.f('ix_payment_account_bcol_user_id'), 'payment_account', ['bcol_user_id'], unique=False)
    op.create_foreign_key('payment_account_payment_method', 'payment_account', 'payment_method', ['payment_method'],
                          ['code'])

    # Update payment account id here
    op.execute(
        'update invoice set payment_account_id = (select account_id from credit_payment_account where id=credit_account_id) where credit_account_id is not null')
    op.execute(
        'update invoice set payment_account_id = (select account_id from bcol_payment_account where id::varchar=bcol_account_id) where bcol_account_id is not null')
    op.execute(
        'update invoice set payment_account_id = (select account_id from internal_payment_account where id=internal_account_id) where internal_account_id is not null')

    # Update bcol_account information in invoice.
    op.execute(
        'update invoice set bcol_account = (select bcol_account_id from bcol_payment_account where id::varchar=bcol_account_id) where bcol_account_id is not null')

    # Update payment account; with bcol information
    conn = op.get_bind()
    # Find all accounts who have linked BCOL accounts
    res = conn.execute("select id,bcol_user_id,bcol_account_id,account_id from bcol_payment_account where bcol_user_id is not null;")
    bcol_payment_accounts = res.fetchall()
    for bcol_payment_account in bcol_payment_accounts:
        bcol_user_id = bcol_payment_account[1]
        bcol_account_id = bcol_payment_account[2]
        account_id = bcol_payment_account[3]

        op.execute(f"update payment_account set bcol_account='{bcol_account_id}', bcol_user_id='{bcol_user_id}', payment_method=\'DRAWDOWN\' where id='{account_id}'")

    # op.execute('update payment_account set payment_method=\'INTERNAL\' where internal_account_id is not null')
    op.execute('update payment_account set payment_method=\'CC\' where payment_method is null')

    # Insert cfs_account details and mark it as inactive, as all the existing accounts are entity based.
    op.execute("insert into cfs_account (account_id, cfs_account, cfs_party, cfs_site, is_active) select account_id, paybc_account, paybc_party, paybc_site, false from credit_payment_account")

    op.create_index(op.f('ix_invoice_bcol_account'), 'invoice', ['bcol_account'], unique=False)
    op.drop_constraint('invoice_credit_account_id_fkey', 'invoice', type_='foreignkey')
    op.drop_constraint('invoice_bcol_account_id_fkey', 'invoice', type_='foreignkey')
    op.drop_constraint('invoice_internal_account_id_fkey', 'invoice', type_='foreignkey')
    op.create_foreign_key('payment_account_payment_account_id', 'invoice', 'payment_account', ['payment_account_id'],
                          ['id'])
    op.drop_column('invoice', 'bcol_account_id')
    op.drop_column('invoice', 'internal_account_id')
    op.drop_column('invoice', 'credit_account_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('payment_account_payment_method', 'payment_account', type_='foreignkey')
    op.drop_index(op.f('ix_payment_account_bcol_user_id'), table_name='payment_account')
    op.drop_index(op.f('ix_payment_account_bcol_account'), table_name='payment_account')
    op.drop_column('payment_account', 'payment_method')
    op.drop_column('payment_account', 'bcol_user_id')
    op.drop_column('payment_account', 'bcol_account')
    op.add_column('invoice', sa.Column('credit_account_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('invoice', sa.Column('internal_account_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('invoice', sa.Column('bcol_account_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_constraint('payment_account_payment_account_id', 'invoice', type_='foreignkey')
    op.create_foreign_key('invoice_internal_account_id_fkey', 'invoice', 'internal_payment_account',
                          ['internal_account_id'], ['id'])
    op.create_foreign_key('invoice_bcol_account_id_fkey', 'invoice', 'bcol_payment_account', ['bcol_account_id'],
                          ['id'])
    op.create_foreign_key('invoice_credit_account_id_fkey', 'invoice', 'credit_payment_account', ['credit_account_id'],
                          ['id'])
    op.drop_index(op.f('ix_invoice_bcol_account'), table_name='invoice')
    op.drop_column('invoice', 'payment_account_id')
    op.drop_column('invoice', 'bcol_account')
    # op.create_table('bcol_payment_account',
    #                 sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    #                 sa.Column('bcol_user_id', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    #                 sa.Column('bcol_account_id', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    #                 sa.Column('account_id', sa.INTEGER(), autoincrement=False, nullable=True),
    #                 sa.ForeignKeyConstraint(['account_id'], ['payment_account.id'],
    #                                         name='bcol_payment_account_account_id_fkey'),
    #                 sa.PrimaryKeyConstraint('id', name='bcol_payment_account_pkey')
    #                 )
    # op.create_index('ix_bcol_payment_account_bcol_user_id', 'bcol_payment_account', ['bcol_user_id'], unique=False)
    # op.create_index('ix_bcol_payment_account_bcol_account_id', 'bcol_payment_account', ['bcol_account_id'],
    #                 unique=False)
    # op.create_index('ix_bcol_payment_account_account_id', 'bcol_payment_account', ['account_id'], unique=False)
    # op.create_table('credit_payment_account',
    #                 sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    #                 sa.Column('corp_number', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    #                 sa.Column('corp_type_code', sa.VARCHAR(length=10), autoincrement=False, nullable=True),
    #                 sa.Column('paybc_account', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    #                 sa.Column('paybc_party', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    #                 sa.Column('paybc_site', sa.VARCHAR(length=50), autoincrement=False, nullable=True),
    #                 sa.Column('account_id', sa.INTEGER(), autoincrement=False, nullable=True),
    #                 sa.ForeignKeyConstraint(['account_id'], ['payment_account.id'],
    #                                         name='credit_payment_account_account_id_fkey'),
    #                 sa.ForeignKeyConstraint(['corp_type_code'], ['corp_type.code'],
    #                                         name='credit_payment_account_corp_type_code_fkey'),
    #                 sa.PrimaryKeyConstraint('id', name='credit_payment_account_pkey')
    #                 )
    # op.create_index('ix_credit_payment_account_paybc_account', 'credit_payment_account', ['paybc_account'],
    #                 unique=False)
    # op.create_index('ix_credit_payment_account_account_id', 'credit_payment_account', ['account_id'], unique=False)
    # op.create_table('internal_payment_account',
    #                 sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    #                 sa.Column('corp_number', sa.VARCHAR(length=20), autoincrement=False, nullable=True),
    #                 sa.Column('corp_type_code', sa.VARCHAR(length=10), autoincrement=False, nullable=True),
    #                 sa.Column('account_id', sa.INTEGER(), autoincrement=False, nullable=True),
    #                 sa.ForeignKeyConstraint(['account_id'], ['payment_account.id'],
    #                                         name='internal_payment_account_account_id_fkey'),
    #                 sa.ForeignKeyConstraint(['corp_type_code'], ['corp_type.code'],
    #                                         name='internal_payment_account_corp_type_code_fkey'),
    #                 sa.PrimaryKeyConstraint('id', name='internal_payment_account_pkey')
    #                 )
    # op.create_index('ix_internal_payment_account_account_id', 'internal_payment_account', ['account_id'], unique=False)
    op.drop_index(op.f('ix_cfs_account_cfs_account'), table_name='cfs_account')
    op.drop_index(op.f('ix_cfs_account_bank_number'), table_name='cfs_account')
    op.drop_index(op.f('ix_cfs_account_bank_name'), table_name='cfs_account')
    op.drop_index(op.f('ix_cfs_account_bank_branch_number'), table_name='cfs_account')
    op.drop_index(op.f('ix_cfs_account_bank_branch'), table_name='cfs_account')
    op.drop_index(op.f('ix_cfs_account_bank_account_number'), table_name='cfs_account')
    op.drop_index(op.f('ix_cfs_account_account_id'), table_name='cfs_account')
    op.drop_table('cfs_account')
    # ### end Alembic commands ###
