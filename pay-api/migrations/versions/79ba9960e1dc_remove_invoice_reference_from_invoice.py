"""remove_invoice_reference_from_invoice

Revision ID: 79ba9960e1dc
Revises: 2ad11d69f0d1
Create Date: 2019-11-14 09:35:21.812569

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "79ba9960e1dc"
down_revision = "2ad11d69f0d1"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("invoice", "invoice_number")
    op.drop_column("invoice", "reference_number")


def downgrade():
    op.add_column(
        "invoice", sa.Column("invoice_number", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "invoice", sa.Column("reference_number", sa.String(length=50), nullable=True)
    )
    op.execute(
        "update "
        "invoice inv  "
        "set "
        "reference_number = inv_ref.reference_number, "
        "invoice_number = inv_ref.invoice_number "
        "from "
        "invoice_reference inv_ref "
        "where "
        "inv.id = inv_ref.invoice_id"
    )
