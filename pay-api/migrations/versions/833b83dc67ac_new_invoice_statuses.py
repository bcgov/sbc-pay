"""New Invoice REFUND statuses

Revision ID: 833b83dc67ac
Revises: 1e62e1c27b08
Create Date: 2022-12-01 09:58:15.463626

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "833b83dc67ac"
down_revision = "1e62e1c27b08"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "update invoice_status_codes set description='Deleted' where code='DELETED'"
    )
    op.execute(
        "insert into invoice_status_codes (code, description) values ('CANCELLED','Cancelled')"
    )
    op.execute(
        "insert into invoice_status_codes (code, description) values ('CREDITED','Credited')"
    )
    pass


def downgrade():
    op.execute(
        "update invoice_status_codes set description='Cancelled' where code='DELETED'"
    )
    op.execute(
        "delete from invoice_status_codes where code in ('CANCELLED','CREDITED')"
    )
    pass
