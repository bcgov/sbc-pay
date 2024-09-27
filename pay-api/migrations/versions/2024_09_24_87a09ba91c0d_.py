"""Drop refund email list, use keycloak instead.

Revision ID: 87a09ba91c0d
Revises: 75a39e02c746
Create Date: 2024-09-24 14:01:25.238895

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
# Note you may see foreign keys with distribution_codes_history
# For disbursement_distribution_code_id, service_fee_distribution_code_id
# Please ignore those lines and don't include in migration.

revision = '87a09ba91c0d'
down_revision = '75a39e02c746'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('DROP SEQUENCE IF EXISTS eft_refund_email_list_id_seq CASCADE')
    op.execute('DROP TABLE IF EXISTS eft_refund_email_list')

def downgrade():
    pass
