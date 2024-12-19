"""add products table, and insert product codes and their payment methods

Revision ID: 695a899f8a25
Revises: 4f3a44eeade8
Create Date: 2024-12-18 11:32:07.538729

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '695a899f8a25'
down_revision = '4f3a44eeade8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'products',
        sa.Column('product_code', sa.String(), nullable=False),
        sa.Column('payment_methods', sa.ARRAY(sa.String()), nullable=True),
        sa.PrimaryKeyConstraint('product_code')
    )

    products_table = sa.table(
        "products",
        sa.column("product_code", sa.String),
        sa.column("payment_methods", sa.ARRAY(sa.String))
    )

    op.bulk_insert(
        products_table,
        [
            {"product_code": "CA_SEARCH", "payment_methods": None},
            {"product_code": "STRR", "payment_methods": None},
            {"product_code": "BCFMS", "payment_methods": None},
            {"product_code": "BCRHP", "payment_methods": None}, 
            {"product_code": "NDS", "payment_methods": None},
            {"product_code": "BUSINESS", "payment_methods": ["PAD", "DIRECT_PAY", "ONLINE_BANKING", "DRAWDOWN"]},
            {"product_code": "DIR_SEARCH", "payment_methods": None},
            {"product_code": "NRO", "payment_methods": ["PAD", "DRAWDOWN"]},
            {"product_code": "RPPR", "payment_methods": ["PAD", "DRAWDOWN"]},
            {"product_code": "VS", "payment_methods": ["PAD", "DRAWDOWN"]},
            {"product_code": "RPT", "payment_methods": ["PAD", "DRAWDOWN"]},
            {"product_code": "BUSINESS_SEARCH", "payment_methods": ["PAD", "DRAWDOWN"]},
            {"product_code": "CSO", "payment_methods": ["PAD", "DRAWDOWN"]},
            {"product_code": "ESRA", "payment_methods": ["PAD", "DRAWDOWN"]},
            {"product_code": "BCA", "payment_methods": ["PAD", "DRAWDOWN"]},
            {"product_code": "PPR", "payment_methods": ["PAD", "DRAWDOWN"]},
            {"product_code": "MHR", "payment_methods": ["PAD", "DRAWDOWN"]},
            {"product_code": "MHR_QSLN", "payment_methods": None},
            {"product_code": "MHR_QSHM", "payment_methods": None},
            {"product_code": "MHR_QSHD", "payment_methods": None}
        ]
    )


def downgrade():
    op.drop_table('products')
