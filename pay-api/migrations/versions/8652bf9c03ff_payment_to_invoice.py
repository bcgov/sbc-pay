"""payment_to_invoice

Revision ID: 8652bf9c03ff
Revises: 20f0cfd54e81
Create Date: 2020-10-01 16:34:34.708440

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import String
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "8652bf9c03ff"
down_revision = "20f0cfd54e81"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    status_code_table = table(
        "invoice_status_code", column("code", String), column("description", String)
    )

    op.bulk_insert(
        status_code_table,
        [{"code": "DELETE_ACCEPTED", "description": "Accepted to Delete"}],
    )
    # Add all columns first
    op.add_column(
        "invoice", sa.Column("payment_method_code", sa.String(length=15), nullable=True)
    )
    op.add_column("payment", sa.Column("amount", sa.Numeric(), nullable=True))
    op.add_column("payment", sa.Column("completed_on", sa.DateTime(), nullable=True))
    op.add_column(
        "payment", sa.Column("invoice_number", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "payment", sa.Column("payment_account_id", sa.Integer(), nullable=True)
    )
    op.alter_column(
        "payment", "created_on", existing_type=postgresql.TIMESTAMP(), nullable=True
    )
    op.alter_column(
        "payment",
        "payment_status_code",
        existing_type=sa.VARCHAR(length=20),
        nullable=True,
    )

    # Select payment method from payment table and update to invoice table.
    conn = op.get_bind()
    res = conn.execute(
        sa.text("select id, payment_method_code, payment_status_code from payment ")
    )
    payments = res.fetchall()

    for payment in payments:
        pay_id = payment[0]
        payment_method = payment[1]
        payment_status = payment[2]

        # Update payment method in invoice
        op.execute(
            f"update invoice set payment_method_code='{payment_method}' where payment_id={pay_id}"
        )

        # Update payment account id to payment table
        op.execute(
            f"update payment set payment_account_id=(select payment_account_id from invoice where payment_id={pay_id}) where id={pay_id}"
        )

        op.execute(
            f"update payment set amount=(select paid from invoice where payment_id={pay_id}) where id={pay_id}"
        )

        op.execute(f"update payment set completed_on=updated_on where id={pay_id}")

        # If payment status is DELETE_ACCEPTED then update that status to invoice.
        if payment_status == "DELETE_ACCEPTED":

            op.execute(
                f"update invoice set invoice_status_code='DELETE_ACCEPTED' where payment_id={pay_id}"
            )

            op.execute(
                f"update payment set payment_status_code='CREATED' where id={pay_id}"
            )

    # Populate invoice number to payment table.
    conn = op.get_bind()
    res = conn.execute(
        sa.text("select id, invoice_status_code, payment_id from invoice ")
    )
    invoices = res.fetchall()
    for invoice in invoices:
        inv_id = invoice[0]
        inv_status = invoice[1]
        pay_id = invoice[2]

        if inv_status == "CREATED" or inv_status == "DELETE_ACCEPTED":
            op.execute(
                f"update payment set invoice_number=(select invoice_number from invoice_reference where invoice_id={inv_id} and status_code='ACTIVE' limit 1) where id={pay_id}"
            )
        elif inv_status == "PAID" or inv_status == "GL_UPDATED":
            op.execute(
                f"update payment set invoice_number=(select invoice_number from invoice_reference where invoice_id={inv_id} and status_code='COMPLETED' limit 1) where id={pay_id} "
            )
        elif inv_status == "DELETED":
            op.execute(
                f"update payment set invoice_number=(select invoice_number from invoice_reference where invoice_id={inv_id} and status_code='CANCELLED' limit 1) where id={pay_id} "
            )

    op.drop_constraint("invoice_payment_id_fkey", "invoice", type_="foreignkey")
    op.create_foreign_key(
        "invoice_payment_method",
        "invoice",
        "payment_method",
        ["payment_method_code"],
        ["code"],
    )
    # op.drop_column('invoice', 'credit_account_id')
    # op.drop_column('invoice', 'internal_account_id')
    op.drop_column("invoice", "payment_id")
    # op.drop_column('invoice', 'bcol_account_id')

    op.create_index(
        op.f("ix_payment_invoice_number"), "payment", ["invoice_number"], unique=False
    )
    op.create_foreign_key(
        "payment_payment_account_id",
        "payment",
        "payment_account",
        ["payment_account_id"],
        ["id"],
    )
    op.drop_column("payment", "updated_by")
    op.drop_column("payment", "created_name")
    op.drop_column("payment", "created_by")
    op.drop_column("payment", "updated_on")
    op.drop_column("payment", "updated_name")

    op.execute(
        "update invoice_status_code set description='Pending' where code='CREATED'"
    )
    op.execute(
        "update invoice_status_code set description='Cancelled' where code='DELETED'"
    )
    op.execute(
        "update invoice_status_code set description='Completed' where code='PAID'"
    )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "payment",
        sa.Column(
            "updated_name", sa.VARCHAR(length=50), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "payment",
        sa.Column(
            "updated_on", postgresql.TIMESTAMP(), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "payment",
        sa.Column(
            "created_by", sa.VARCHAR(length=50), autoincrement=False, nullable=False
        ),
    )
    op.add_column(
        "payment",
        sa.Column(
            "created_name", sa.VARCHAR(length=100), autoincrement=False, nullable=True
        ),
    )
    op.add_column(
        "payment",
        sa.Column(
            "updated_by", sa.VARCHAR(length=50), autoincrement=False, nullable=True
        ),
    )
    op.drop_constraint("payment_payment_account_id", "payment", type_="foreignkey")
    op.drop_index(op.f("ix_payment_invoice_number"), table_name="payment")
    op.alter_column(
        "payment",
        "payment_status_code",
        existing_type=sa.VARCHAR(length=20),
        nullable=False,
    )
    op.alter_column(
        "payment", "created_on", existing_type=postgresql.TIMESTAMP(), nullable=False
    )
    op.drop_column("payment", "payment_account_id")
    op.drop_column("payment", "invoice_number")
    op.drop_column("payment", "completed_on")
    op.drop_column("payment", "amount")
    # op.add_column('invoice', sa.Column('bcol_account_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column(
        "invoice",
        sa.Column("payment_id", sa.INTEGER(), autoincrement=False, nullable=False),
    )
    # op.add_column('invoice', sa.Column('internal_account_id', sa.INTEGER(), autoincrement=False, nullable=True))
    # op.add_column('invoice', sa.Column('credit_account_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_constraint("invoice_payment_method", "invoice", type_="foreignkey")
    op.create_foreign_key(
        "invoice_payment_id_fkey", "invoice", "payment", ["payment_id"], ["id"]
    )
    op.drop_column("invoice", "payment_method_code")

    op.execute("delete from invoice_status_code where code='DELETE_ACCEPTED'")
    # ### end Alembic commands ###
