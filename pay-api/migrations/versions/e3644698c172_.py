"""Sync up using python manage.py db migrate.

Revision ID: e3644698c172
Revises: 175c11863186
Create Date: 2022-05-12 12:26:30.116376

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e3644698c172"
down_revision = "175c11863186"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("update account_fees set created_on = now() where created_on is null")
    op.execute("update account_fees set created_by = 'SYSTEM' where created_by is null")
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "account_fees",
        "created_on",
        existing_type=postgresql.TIMESTAMP(),
        nullable=False,
    )
    op.alter_column(
        "account_fees",
        "created_by",
        existing_type=sa.VARCHAR(length=50),
        nullable=False,
    )
    # Remove hand made indexes.
    op.execute("DROP INDEX IF EXISTS invoices_payment_method_code_idx")
    op.create_index(
        op.f("ix_invoices_payment_method_code"),
        "invoices",
        ["payment_method_code"],
        unique=False,
    )
    op.execute("DROP INDEX IF EXISTS routing_slips_status_idx")
    op.create_index(
        op.f("ix_routing_slips_status"), "routing_slips", ["status"], unique=False
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_routing_slips_status"), table_name="routing_slips")
    op.create_index(
        "routing_slips_status_idx", "routing_slips", ["status"], unique=False
    )
    op.drop_index(op.f("ix_invoices_payment_method_code"), table_name="invoices")
    op.create_index(
        "invoices_payment_method_code_idx",
        "invoices",
        ["payment_method_code"],
        unique=False,
    )
    op.alter_column(
        "account_fees", "created_by", existing_type=sa.VARCHAR(length=50), nullable=True
    )
    op.alter_column(
        "account_fees",
        "created_on",
        existing_type=postgresql.TIMESTAMP(),
        nullable=True,
    )
    # ### end Alembic commands ###
