"""cfs_account_status

Revision ID: 70af1f70f6bf
Revises: 8f7565cf50c1
Create Date: 2020-10-13 12:08:24.062697

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "70af1f70f6bf"
down_revision = "8f7565cf50c1"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    cfs_account_status_code = op.create_table(
        "cfs_account_status_code",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )

    op.bulk_insert(
        cfs_account_status_code,
        [
            {"code": "PENDING", "description": "CFS Account creation is pending."},
            {"code": "ACTIVE", "description": "CFS Account is active."},
            {"code": "INACTIVE", "description": "CFS Account is not in use."},
            {"code": "FREEZE", "description": "CFS Account is frozen."},
        ],
    )

    op.create_table(
        "cfs_account_version",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column(
            "cfs_account", sa.String(length=50), autoincrement=False, nullable=True
        ),
        sa.Column(
            "cfs_party", sa.String(length=50), autoincrement=False, nullable=True
        ),
        sa.Column("cfs_site", sa.String(length=50), autoincrement=False, nullable=True),
        sa.Column(
            "payment_instrument_number",
            sa.String(length=50),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "contact_party", sa.String(length=50), autoincrement=False, nullable=True
        ),
        sa.Column(
            "bank_name", sa.String(length=50), autoincrement=False, nullable=True
        ),
        sa.Column(
            "bank_number", sa.String(length=50), autoincrement=False, nullable=True
        ),
        sa.Column(
            "bank_branch", sa.String(length=50), autoincrement=False, nullable=True
        ),
        sa.Column(
            "bank_branch_number",
            sa.String(length=50),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "bank_account_number",
            sa.String(length=50),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("status", sa.String(length=20), autoincrement=False, nullable=True),
        sa.Column("account_id", sa.Integer(), autoincrement=False, nullable=True),
        sa.Column(
            "transaction_id", sa.BigInteger(), autoincrement=False, nullable=False
        ),
        sa.Column("end_transaction_id", sa.BigInteger(), nullable=True),
        sa.Column("operation_type", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", "transaction_id"),
    )
    op.create_index(
        op.f("ix_cfs_account_version_account_id"),
        "cfs_account_version",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cfs_account_version_bank_account_number"),
        "cfs_account_version",
        ["bank_account_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cfs_account_version_bank_branch"),
        "cfs_account_version",
        ["bank_branch"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cfs_account_version_bank_branch_number"),
        "cfs_account_version",
        ["bank_branch_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cfs_account_version_bank_name"),
        "cfs_account_version",
        ["bank_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cfs_account_version_bank_number"),
        "cfs_account_version",
        ["bank_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cfs_account_version_cfs_account"),
        "cfs_account_version",
        ["cfs_account"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cfs_account_version_end_transaction_id"),
        "cfs_account_version",
        ["end_transaction_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cfs_account_version_operation_type"),
        "cfs_account_version",
        ["operation_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cfs_account_version_transaction_id"),
        "cfs_account_version",
        ["transaction_id"],
        unique=False,
    )

    op.add_column(
        "cfs_account", sa.Column("status", sa.String(length=20), nullable=True)
    )
    op.create_foreign_key(
        "cfs_account_status_code_fk",
        "cfs_account",
        "cfs_account_status_code",
        ["status"],
        ["code"],
    )

    # Set status based on is_active flag
    op.execute("update cfs_account set status='ACTIVE' where is_active=True")
    op.execute("update cfs_account set status='INACTIVE' where is_active=False")

    op.drop_column("cfs_account", "is_active")
    op.alter_column(
        "invoice",
        "payment_method_code",
        existing_type=sa.VARCHAR(length=15),
        nullable=False,
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "invoice",
        "payment_method_code",
        existing_type=sa.VARCHAR(length=15),
        nullable=True,
    )
    op.add_column(
        "cfs_account",
        sa.Column("is_active", sa.BOOLEAN(), autoincrement=False, nullable=True),
    )
    # Set status based on is_active flag
    op.execute("update cfs_account set is_active=True where status='ACTIVE'")
    op.execute("update cfs_account set is_active=False where status='INACTIVE'")

    op.drop_constraint("cfs_account_status_code_fk", "cfs_account", type_="foreignkey")
    op.drop_column("cfs_account", "status")

    op.drop_index(
        op.f("ix_cfs_account_version_transaction_id"), table_name="cfs_account_version"
    )
    op.drop_index(
        op.f("ix_cfs_account_version_operation_type"), table_name="cfs_account_version"
    )
    op.drop_index(
        op.f("ix_cfs_account_version_end_transaction_id"),
        table_name="cfs_account_version",
    )
    op.drop_index(
        op.f("ix_cfs_account_version_cfs_account"), table_name="cfs_account_version"
    )
    op.drop_index(
        op.f("ix_cfs_account_version_bank_number"), table_name="cfs_account_version"
    )
    op.drop_index(
        op.f("ix_cfs_account_version_bank_name"), table_name="cfs_account_version"
    )
    op.drop_index(
        op.f("ix_cfs_account_version_bank_branch_number"),
        table_name="cfs_account_version",
    )
    op.drop_index(
        op.f("ix_cfs_account_version_bank_branch"), table_name="cfs_account_version"
    )
    op.drop_index(
        op.f("ix_cfs_account_version_bank_account_number"),
        table_name="cfs_account_version",
    )
    op.drop_index(
        op.f("ix_cfs_account_version_account_id"), table_name="cfs_account_version"
    )
    op.drop_table("cfs_account_version")
    op.drop_table("cfs_account_status_code")
    # ### end Alembic commands ###
