"""add_eft_cas_supplier_site

Revision ID: 4f3a44eeade8
Revises: c6f04824d529
Create Date: 2024-12-04 16:16:39.574734

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '4f3a44eeade8'
down_revision = 'c6f04824d529'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "eft_short_names", sa.Column("cas_supplier_site", sa.String(25), nullable=True)
    )
    op.add_column(
        "eft_short_names_history", sa.Column("cas_supplier_site", sa.String(25), nullable=True)
    )
    op.add_column(
        "eft_refunds", sa.Column("cas_supplier_site", sa.String(25), nullable=False)
    )


def downgrade():
    op.drop_column("eft_refunds", "cas_supplier_site")
    op.drop_column("eft_short_names_history", "cas_supplier_site")
    op.drop_column("eft_short_names", "cas_supplier_site")
