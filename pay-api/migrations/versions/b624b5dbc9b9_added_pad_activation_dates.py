"""added pad activation dates

Revision ID: b624b5dbc9b9
Revises: 7c19ee3a58aa
Create Date: 2020-11-16 15:53:01.664968

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "b624b5dbc9b9"
down_revision = "7c19ee3a58aa"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "payment_account",
        sa.Column("pad_tos_accepted_by", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "payment_account",
        sa.Column("pad_tos_accepted_date", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "payment_account_version",
        sa.Column(
            "pad_tos_accepted_by",
            sa.String(length=50),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "payment_account_version",
        sa.Column(
            "pad_tos_accepted_date", sa.DateTime(), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "payment_account",
        sa.Column("pad_activation_date", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "payment_account_version",
        sa.Column(
            "pad_activation_date", sa.DateTime(), autoincrement=False, nullable=True
        ),
    )

    error_code_table = table(
        "error_code",
        column("code", String),
        column("title", String),
        column("detail", String),
    )
    op.bulk_insert(
        error_code_table,
        [
            {
                "code": "ACCOUNT_IN_PAD_CONFIRMATION_PERIOD",
                "title": "Account in PAD confirmation period",
                "detail": "Your account is in the 3 day PAD confirmation period. You will be able to do transactions "
                "only after the period is over.",
            }
        ],
    )

    op.alter_column(
        "cfs_account",
        "status",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=40),
        existing_nullable=True,
    )
    op.alter_column(
        "cfs_account_version",
        "status",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=40),
        existing_nullable=True,
        autoincrement=False,
    )

    op.alter_column(
        "cfs_account_status_code",
        "code",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=40),
    )

    cfs_account_status_code_table = table(
        "cfs_account_status_code", column("code", String), column("description", String)
    )

    op.bulk_insert(
        cfs_account_status_code_table,
        [
            {
                "code": "PENDING_PAD_ACTIVATION",
                "description": "Account in PAD Confirmation Period.",
            },
        ],
    )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("payment_account", "pad_tos_accepted_date")
    op.drop_column("payment_account", "pad_tos_accepted_by")
    op.drop_column("payment_account", "pad_activation_date")
    op.drop_column("payment_account_version", "pad_tos_accepted_date")
    op.drop_column("payment_account_version", "pad_tos_accepted_by")
    op.drop_column("payment_account_version", "pad_activation_date")

    op.alter_column(
        "cfs_account_version",
        "status",
        existing_type=sa.String(length=40),
        type_=sa.VARCHAR(length=20),
        existing_nullable=True,
        autoincrement=False,
    )
    op.alter_column(
        "cfs_account",
        "status",
        existing_type=sa.String(length=40),
        type_=sa.VARCHAR(length=20),
        existing_nullable=True,
    )
    op.execute(
        "delete from cfs_account_status_code where code='PENDING_PAD_ACTIVATION'"
    )
    op.execute("delete from error_code where code='ACCOUNT_IN_PAD_CONFIRMATION_PERIOD'")
    # ### end Alembic commands ###
