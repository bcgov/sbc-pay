"""add_non_gov_disbursement_config

Revision ID: d4e5f6a7b8c9
Revises: 9b1c4d7e8f90
Create Date: 2026-06-09 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "9b1c4d7e8f90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "non_gov_disbursement_config",
        sa.Column("corp_type_code", sa.String(10), sa.ForeignKey("corp_types.code"), primary_key=True),
        sa.Column("cas_supplier_number", sa.String(50), nullable=True),
        sa.Column("cas_supplier_site", sa.String(10), nullable=True),
        sa.Column("disabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_on", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_on", sa.DateTime, nullable=True),
        sa.Column("created_by", sa.String(50), nullable=False, server_default="migration"),
        sa.Column("created_name", sa.String(100), nullable=True),
        sa.Column("updated_by", sa.String(50), nullable=True),
        sa.Column("updated_name", sa.String(100), nullable=True),
    )


def downgrade():
    op.drop_table("non_gov_disbursement_config")
