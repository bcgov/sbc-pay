"""Migration to populate new service fee columns.

Revision ID: 33bbd4d9a85c
Revises: f4a1388844ed
Create Date: 2023-03-21 13:57:05.923514

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "33bbd4d9a85c"
down_revision = "f4a1388844ed"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "corp_types", "bcol_fee_code", new_column_name="bcol_code_full_service_fee"
    )
    op.add_column(
        "corp_types",
        sa.Column("bcol_code_partial_service_fee", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "corp_types",
        sa.Column("bcol_code_no_service_fee", sa.String(length=20), nullable=True),
    )
    op.execute(
        "update corp_types set bcol_code_partial_service_fee = REPLACE (bcol_code_full_service_fee, '1', '2'), bcol_code_no_service_fee = REPLACE (bcol_code_full_service_fee, '1', '3')"
    )


def downgrade():
    op.alter_column(
        "corp_types", "bcol_code_full_service_fee", new_column_name="bcol_fee_code"
    )
    op.drop_column("corp_types", "bcol_code_no_service_fee")
    op.drop_column("corp_types", "bcol_code_partial_service_fee")
