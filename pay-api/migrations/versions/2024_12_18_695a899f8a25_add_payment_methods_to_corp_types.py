"""add payment_methods column to corp_types table, and insert payment methods based on product

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
    op.add_column(
        'corp_types',
        sa.Column('payment_methods', sa.ARRAY(sa.String()), nullable=True)
    )

    op.execute("""
        UPDATE corp_types 
        SET payment_methods = 
            CASE product
                WHEN 'BUSINESS' THEN ARRAY['PAD', 'DIRECT_PAY', 'ONLINE_BANKING', 'DRAWDOWN']
                WHEN 'NRO' THEN ARRAY['PAD', 'DRAWDOWN']
                WHEN 'RPPR' THEN ARRAY['PAD', 'DRAWDOWN']
                WHEN 'VS' THEN ARRAY['PAD', 'DRAWDOWN']
                WHEN 'RPT' THEN ARRAY['PAD', 'DRAWDOWN']
                WHEN 'BUSINESS_SEARCH' THEN ARRAY['PAD', 'DRAWDOWN']
                WHEN 'CSO' THEN ARRAY['PAD', 'DRAWDOWN']
                WHEN 'ESRA' THEN ARRAY['PAD', 'DRAWDOWN']
                WHEN 'BCA' THEN ARRAY['PAD', 'DRAWDOWN']
                WHEN 'PPR' THEN ARRAY['PAD', 'DRAWDOWN']
                WHEN 'MHR' THEN ARRAY['PAD', 'DRAWDOWN']
                ELSE NULL
            END
        WHERE product IS NOT NULL
    """)


def downgrade():
    op.drop_column('corp_types', 'payment_methods')
