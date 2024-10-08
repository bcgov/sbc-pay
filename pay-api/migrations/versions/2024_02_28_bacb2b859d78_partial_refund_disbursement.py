"""19875 - Disbursement Date and Status for Partial Refunds.

Revision ID: bacb2b859d78
Revises: 1ec047cf4308
Create Date: 2024-02-28 10:59:05.732786

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bacb2b859d78"
down_revision = "1ec047cf4308"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "refunds_partial",
        sa.Column("disbursement_status_code", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "refunds_partial", sa.Column("disbursement_date", sa.Date(), nullable=True)
    )
    op.create_foreign_key(
        None,
        "refunds_partial",
        "disbursement_status_codes",
        ["disbursement_status_code"],
        ["code"],
    )

    op.add_column(
        "refunds_partial_version",
        sa.Column(
            "disbursement_status_code",
            sa.String(length=20),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "refunds_partial_version",
        sa.Column("disbursement_date", sa.Date(), autoincrement=False, nullable=True),
    )


def downgrade():
    op.drop_constraint(None, "refunds_partial", type_="foreignkey")
    op.drop_column("refunds_partial", "disbursement_status_code")
    op.drop_column("refunds_partial", "disbursement_date")

    op.drop_column("refunds_partial_version", "disbursement_status_code")
    op.drop_column("refunds_partial_version", "disbursement_date")
