"""Rename ejv_invoice_links to ejv_links, alter invoice_id to link_id, removed foreign constraint, and added link_type column

Revision ID: 04b8a7bed74e
Revises: bacb2b859d78
Create Date: 2024-03-06 11:40:00.153387

"""

from alembic import op
import sqlalchemy as sa

from pay_api.utils.enums import EJVLinkType

# revision identifiers, used by Alembic.
revision = "04b8a7bed74e"
down_revision = "bacb2b859d78"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ejv_invoice_links", sa.Column("link_type", sa.String(length=20), nullable=True)
    )
    op.drop_constraint(
        "ejv_invoice_links_invoice_id_fkey", "ejv_invoice_links", type_="foreignkey"
    )
    op.drop_index(
        op.f("ix_ejv_invoice_links_invoice_id"), table_name="ejv_invoice_links"
    )
    op.alter_column(
        "ejv_invoice_links",
        "invoice_id",
        new_column_name="link_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.rename_table("ejv_invoice_links", "ejv_links")
    # as there is no data for partial refunds yet.
    op.execute(f"UPDATE ejv_links set link_type='{EJVLinkType.INVOICE.value}'")

    op.create_index(
        "ix_ejv_links_link_type_link_id",
        "ejv_links",
        ["link_type", "link_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_ejv_links_link_type_link_id", table_name="ejv_links")
    op.rename_table("ejv_links", "ejv_invoice_links")
    op.alter_column(
        "ejv_invoice_links",
        "link_id",
        new_column_name="invoice_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_index(
        op.f("ix_ejv_invoice_links_invoice_id"),
        "ejv_invoice_links",
        ["invoice_id"],
        unique=False,
    )
    op.drop_column("ejv_invoice_links", "link_type")
    op.create_foreign_key(
        "ejv_invoice_links_invoice_id_fkey",
        "ejv_invoice_links",
        "invoices",
        ["invoice_id"],
        ["id"],
    )
