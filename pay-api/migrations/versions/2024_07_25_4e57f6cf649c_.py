"""

Revision ID: 4e57f6cf649c
Revises: f9c15c7f29f5
Create Date: 2024-07-25 16:03:51.968355

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4e57f6cf649c"
down_revision = "f9c15c7f29f5"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute("DROP SEQUENCE IF EXISTS eft_refund_email_list_id_seq CASCADE")
    op.execute("DROP TABLE IF EXISTS eft_refund_email_list")
    op.create_table(
        "eft_refund_email_list",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("first_name", sa.String(25), nullable=True),
        sa.Column("last_name", sa.String(25), nullable=True),
        sa.Column("email", sa.String(25), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("eft_credit_invoice_links", schema=None) as batch_op:
        batch_op.alter_column(
            "status_code", existing_type=sa.VARCHAR(length=25), nullable=False
        )

    with op.batch_alter_table("eft_refunds", schema=None) as batch_op:
        batch_op.alter_column("comment", existing_type=sa.VARCHAR(), nullable=False)

    with op.batch_alter_table("ejv_links", schema=None) as batch_op:
        batch_op.alter_column(
            "link_type",
            existing_type=sa.VARCHAR(length=20),
            type_=sa.String(length=50),
            existing_nullable=True,
        )
        batch_op.drop_index("ix_ejv_invoice_links_ejv_header_id")
        batch_op.drop_index("ix_ejv_links_link_type_link_id")
        batch_op.create_index(
            batch_op.f("ix_ejv_links_ejv_header_id"), ["ejv_header_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ejv_links_link_id"), ["link_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ejv_links_link_type"), ["link_type"], unique=False
        )

    with op.batch_alter_table("refunds_partial", schema=None) as batch_op:
        batch_op.alter_column(
            "disbursement_date",
            existing_type=sa.DATE(),
            type_=sa.DateTime(),
            existing_nullable=True,
        )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("refunds_partial", schema=None) as batch_op:
        batch_op.alter_column(
            "disbursement_date",
            existing_type=sa.DateTime(),
            type_=sa.DATE(),
            existing_nullable=True,
        )

    with op.batch_alter_table("ejv_links", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ejv_links_link_type"))
        batch_op.drop_index(batch_op.f("ix_ejv_links_link_id"))
        batch_op.drop_index(batch_op.f("ix_ejv_links_ejv_header_id"))
        batch_op.create_index(
            "ix_ejv_links_link_type_link_id", ["link_type", "link_id"], unique=False
        )
        batch_op.create_index(
            "ix_ejv_invoice_links_ejv_header_id", ["ejv_header_id"], unique=False
        )
        batch_op.alter_column(
            "link_type",
            existing_type=sa.String(length=50),
            type_=sa.VARCHAR(length=20),
            existing_nullable=True,
        )

    with op.batch_alter_table("eft_refunds", schema=None) as batch_op:
        batch_op.alter_column("comment", existing_type=sa.VARCHAR(), nullable=True)

    with op.batch_alter_table("eft_credit_invoice_links", schema=None) as batch_op:
        batch_op.alter_column(
            "status_code", existing_type=sa.VARCHAR(length=25), nullable=True
        )

    with op.batch_alter_table("distribution_codes_history", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.drop_constraint(None, type_="foreignkey")
    # ### end Alembic commands ###
