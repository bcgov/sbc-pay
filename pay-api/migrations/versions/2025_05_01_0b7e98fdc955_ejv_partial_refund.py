"""Add partial refund for EJV and add columns to refunds_partial

Revision ID: 0b7e98fdc955
Revises: 706b28ee3b37
Create Date: 2025-05-01 22:16:30.628912

"""
from alembic import op
import sqlalchemy as sa

from pay_api.utils.enums import PaymentMethod, RefundsPartialStatus


# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '0b7e98fdc955'
down_revision = '706b28ee3b37'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE payment_methods
        SET partial_refund = true
        WHERE code IN (:ejv_code)
    """, {"ejv_code": PaymentMethod.EJV.value})

    op.add_column(
        "refunds_partial", sa.Column("status", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "refunds_partial", sa.Column("gl_error", sa.String(length=250), nullable=True)
    )

    op.execute(f"""
        UPDATE refunds_partial
        SET status = '{RefundsPartialStatus.REFUND_REQUESTED.value}'
        WHERE gl_posted IS NULL
    """)

    op.execute(f"""
        UPDATE refunds_partial
        SET status = '{RefundsPartialStatus.REFUND_PROCESSED.value}'
        WHERE gl_posted IS NOT NULL
    """)


def downgrade():
    op.execute(f"""
        UPDATE payment_methods
        SET partial_refund = false
        WHERE code IN ('{PaymentMethod.EJV.value}')
    """)    
    op.drop_column("refunds_partial", "status")
    op.drop_column("refunds_partial", "gl_error")
