"""new_payment_method_tables

Revision ID: 1283463d3b4a
Revises: 56c5db141909
Create Date: 2020-09-16 17:02:36.571456

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "1283463d3b4a"
down_revision = "56c5db141909"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.alter_column(
        "payment",
        "payment_method_code",
        existing_type=sa.VARCHAR(length=10),
        type_=sa.String(length=15),
        existing_nullable=False,
    )
    op.alter_column(
        "payment_method",
        "code",
        existing_type=sa.VARCHAR(length=10),
        type_=sa.String(length=15),
    )

    payment_method_table = table(
        "payment_method", column("code", String), column("description", String)
    )

    op.bulk_insert(
        payment_method_table,
        [
            {"code": "EFT", "description": "Electronic Funds Transfer"},
            {"code": "WIRE", "description": "Wire Transfer"},
            {"code": "ONLINE_BANKING", "description": "Online Banking"},
            {"code": "PAD", "description": "Pre Authorized Debit"},
            {"code": "EJV", "description": "Electronic Journal Voucher"},
        ],
    )

    op.create_table(
        "daily_payment_batch",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_on", sa.DateTime(), nullable=False),
        sa.Column("file_reference", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ejv_batch",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_on", sa.DateTime(), nullable=False),
        sa.Column("is_distribution", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "invoice_batch",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_on", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "daily_payment_batch_link",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["daily_payment_batch.id"],
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoice.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ejv_batch_link",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["ejv_batch.id"],
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoice.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "invoice_batch_link",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["invoice_batch.id"],
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoice.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # op.drop_index('ix_internal_payment_account_account_id', table_name='internal_payment_account')
    # op.drop_table('internal_payment_account')
    # op.drop_index('ix_credit_payment_account_account_id', table_name='credit_payment_account')
    # op.drop_index('ix_credit_payment_account_paybc_account', table_name='credit_payment_account')
    # op.drop_table('credit_payment_account')
    # op.drop_index('ix_bcol_payment_account_account_id', table_name='bcol_payment_account')
    # op.drop_index('ix_bcol_payment_account_bcol_account_id', table_name='bcol_payment_account')
    # op.drop_index('ix_bcol_payment_account_bcol_user_id', table_name='bcol_payment_account')
    # op.drop_table('bcol_payment_account')
    op.add_column(
        "cfs_account", sa.Column("contact_party", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "cfs_account",
        sa.Column("payment_instrument_number", sa.String(length=50), nullable=True),
    )
    op.add_column("invoice", sa.Column("cfs_account_id", sa.Integer(), nullable=True))

    # Update invoice which have credit_account_id with matching details from cfs_account
    conn = op.get_bind()
    res = conn.execute(
        sa.text(
            "select cfs.id, credit.id from cfs_account cfs, credit_payment_account credit "
            "where credit.paybc_account=cfs.cfs_account and credit.account_id=cfs.account_id;"
        )
    )
    cfs_accounts = res.fetchall()
    for cfs_account in cfs_accounts:
        cfs_id = cfs_account[0]
        credit_id = cfs_account[1]

        op.execute(
            f"update invoice set cfs_account_id='{cfs_id}' where credit_account_id='{credit_id}'"
        )

    op.create_foreign_key(
        "fk_cfs_account_id", "invoice", "cfs_account", ["cfs_account_id"], ["id"]
    )
    op.add_column("payment_account", sa.Column("billable", sa.Boolean(), nullable=True))
    op.add_column("payment_account", sa.Column("credit", sa.Float(), nullable=True))
    op.add_column(
        "payment_account", sa.Column("running_balance", sa.Float(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("payment_account", "running_balance")
    op.drop_column("payment_account", "credit")
    op.drop_column("payment_account", "billable")
    op.drop_constraint("fk_cfs_account_id", "invoice", type_="foreignkey")
    op.drop_column("invoice", "cfs_account_id")
    op.drop_column("cfs_account", "payment_instrument_number")
    op.drop_column("cfs_account", "contact_party")
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
    op.drop_table("invoice_batch_link")
    op.drop_table("ejv_batch_link")
    op.drop_table("daily_payment_batch_link")
    op.drop_table("invoice_batch")
    op.drop_table("ejv_batch")
    op.drop_table("daily_payment_batch")

    op.execute(
        "delete from payment_method where code in ('EFT', 'WIRE', 'ONLINE_BANKING', 'PAD', 'EJV')"
    )
    op.alter_column(
        "payment_method",
        "code",
        existing_type=sa.String(length=15),
        type_=sa.VARCHAR(length=10),
    )
    op.alter_column(
        "payment",
        "payment_method_code",
        existing_type=sa.String(length=15),
        type_=sa.VARCHAR(length=10),
        existing_nullable=False,
    )
    # ### end Alembic commands ###
