"""add_non_gov_disbursement_config

Revision ID: d4e5f6a7b8c9
Revises: cb622dbbf69d
Create Date: 2026-06-09 00:00:00.000000

"""
import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import column, table

revision = "d4e5f6a7b8c9"
down_revision = "cb622dbbf69d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "non_gov_disbursement_config",
        sa.Column("corp_type_code", sa.String(10), sa.ForeignKey("corp_types.code"), primary_key=True),
        sa.Column("cas_supplier_number", sa.String(50), nullable=False),
        sa.Column("cas_supplier_site", sa.String(10), nullable=False),
    )

    non_gov_disbursement_config = table(
        "non_gov_disbursement_config",
        column("corp_type_code", sa.String),
        column("cas_supplier_number", sa.String),
        column("cas_supplier_site", sa.String),
    )

    bca_supplier_number = os.getenv("BCA_SUPPLIER_NUMBER", "")
    bca_supplier_location = os.getenv("BCA_SUPPLIER_LOCATION", "")

    if bca_supplier_number and bca_supplier_location:
        op.bulk_insert(
            non_gov_disbursement_config,
            [
                {
                    "corp_type_code": "BCA",
                    "cas_supplier_number": bca_supplier_number,
                    "cas_supplier_site": bca_supplier_location,
                }
            ],
        )


def downgrade():
    op.drop_table("non_gov_disbursement_config")
