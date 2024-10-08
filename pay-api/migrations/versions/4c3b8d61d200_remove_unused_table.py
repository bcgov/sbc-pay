"""remove_unused_table

Revision ID: 4c3b8d61d200
Revises: 099ba5cf19a3
Create Date: 2021-07-05 13:40:58.106791

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4c3b8d61d200"
down_revision = "099ba5cf19a3"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute("DROP INDEX IF EXISTS ix_bcol_payment_account_account_id")
    op.execute("DROP INDEX IF EXISTS ix_bcol_payment_account_bcol_account_id")
    op.execute("DROP INDEX IF EXISTS ix_bcol_payment_account_bcol_account_id")
    op.execute("DROP TABLE IF EXISTS bcol_payment_account")

    op.execute("DROP INDEX IF EXISTS ix_credit_payment_account_account_id")
    op.execute("DROP INDEX IF EXISTS ix_credit_payment_account_paybc_account")
    op.execute("DROP TABLE IF EXISTS credit_payment_account")

    op.execute("DROP INDEX IF EXISTS ix_internal_payment_account_account_id")
    op.execute("DROP TABLE IF EXISTS internal_payment_account")

    op.execute("ALTER TABLE invoices DROP COLUMN IF EXISTS internal_account_id")
    op.execute("ALTER TABLE invoices DROP COLUMN IF EXISTS credit_account_id")
    op.execute("ALTER TABLE invoices DROP COLUMN IF EXISTS bcol_account_id")
    # op.drop_index('ix_bcol_payment_account_account_id', table_name='bcol_payment_account')
    # op.drop_index('ix_bcol_payment_account_bcol_account_id', table_name='bcol_payment_account')
    # op.drop_index('ix_bcol_payment_account_bcol_user_id', table_name='bcol_payment_account')
    # op.drop_table('bcol_payment_account')
    # op.drop_index('ix_credit_payment_account_account_id', table_name='credit_payment_account')
    # op.drop_index('ix_credit_payment_account_paybc_account', table_name='credit_payment_account')
    # op.drop_table('credit_payment_account')
    # op.drop_index('ix_internal_payment_account_account_id', table_name='internal_payment_account')
    # op.drop_table('internal_payment_account')
    # op.drop_column('invoices', 'internal_account_id')
    # op.drop_column('invoices', 'credit_account_id')
    # op.drop_column('invoices', 'bcol_account_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "invoices",
        sa.Column("bcol_account_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "credit_account_id", sa.INTEGER(), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "internal_account_id", sa.INTEGER(), autoincrement=False, nullable=True
        ),
    )
    op.create_table(
        "internal_payment_account",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column(
            "corp_number", sa.VARCHAR(length=20), autoincrement=False, nullable=True
        ),
        sa.Column(
            "corp_type_code", sa.VARCHAR(length=10), autoincrement=False, nullable=True
        ),
        sa.Column("account_id", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["payment_accounts.id"],
            name="internal_payment_accounts_account_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["corp_type_code"],
            ["corp_types.code"],
            name="internal_payment_account_corp_types_code_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="internal_payment_account_pkey"),
    )
    op.create_index(
        "ix_internal_payment_account_account_id",
        "internal_payment_account",
        ["account_id"],
        unique=False,
    )
    op.create_table(
        "credit_payment_account",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column(
            "corp_number", sa.VARCHAR(length=20), autoincrement=False, nullable=True
        ),
        sa.Column(
            "corp_type_code", sa.VARCHAR(length=10), autoincrement=False, nullable=True
        ),
        sa.Column(
            "paybc_account", sa.VARCHAR(length=50), autoincrement=False, nullable=True
        ),
        sa.Column(
            "paybc_party", sa.VARCHAR(length=50), autoincrement=False, nullable=True
        ),
        sa.Column(
            "paybc_site", sa.VARCHAR(length=50), autoincrement=False, nullable=True
        ),
        sa.Column("account_id", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["payment_accounts.id"],
            name="credit_payment_accounts_account_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["corp_type_code"],
            ["corp_types.code"],
            name="credit_payment_account_corp_types_code_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="credit_payment_account_pkey"),
    )
    op.create_index(
        "ix_credit_payment_account_paybc_account",
        "credit_payment_account",
        ["paybc_account"],
        unique=False,
    )
    op.create_index(
        "ix_credit_payment_account_account_id",
        "credit_payment_account",
        ["account_id"],
        unique=False,
    )
    op.create_table(
        "bcol_payment_account",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column(
            "bcol_user_id", sa.VARCHAR(length=50), autoincrement=False, nullable=True
        ),
        sa.Column(
            "bcol_account_id", sa.VARCHAR(length=50), autoincrement=False, nullable=True
        ),
        sa.Column("account_id", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["payment_accounts.id"],
            name="bcol_payment_accounts_account_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="bcol_payment_account_pkey"),
    )
    op.create_index(
        "ix_bcol_payment_account_bcol_user_id",
        "bcol_payment_account",
        ["bcol_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_bcol_payment_account_bcol_account_id",
        "bcol_payment_account",
        ["bcol_account_id"],
        unique=False,
    )
    op.create_index(
        "ix_bcol_payment_account_account_id",
        "bcol_payment_account",
        ["account_id"],
        unique=False,
    )
    # ### end Alembic commands ###
