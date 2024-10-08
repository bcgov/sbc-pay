"""eft_processing

Revision ID: 456234145e5e
Revises: 3a21a14b4137
Create Date: 2023-09-28 13:11:49.061949

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "456234145e5e"
down_revision = "3a21a14b4137"
branch_labels = None
depends_on = None


def upgrade():
    process_status_codes_table = op.create_table(
        "eft_process_status_codes",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )

    op.bulk_insert(
        process_status_codes_table,
        [
            {
                "code": "COMPLETED",
                "description": "Record or File was able to be fully processed.",
            },
            {
                "code": "INPROGRESS",
                "description": "Record or File processing in progress.",
            },
            {"code": "FAILED", "description": "Record or File failed to process."},
            {
                "code": "PARTIAL",
                "description": "Record or File was partially processed as there were some errors.",
            },
        ],
    )

    op.create_table(
        "eft_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("completed_on", sa.DateTime(), nullable=True),
        sa.Column("created_on", sa.DateTime(), nullable=False),
        sa.Column("deposit_from_date", sa.DateTime(), nullable=True),
        sa.Column("deposit_to_date", sa.DateTime(), nullable=True),
        sa.Column("file_creation_date", sa.DateTime(), nullable=True),
        sa.Column("file_ref", sa.String(), nullable=False),
        sa.Column("number_of_details", sa.Integer(), nullable=True),
        sa.Column("status_code", sa.String(length=20), nullable=False),
        sa.Column("total_deposit_cents", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["status_code"], ["eft_process_status_codes.code"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "eft_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("created_on", sa.DateTime(), nullable=False),
        sa.Column("completed_on", sa.DateTime(), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("line_type", sa.String(20), nullable=False),
        sa.Column("sequence_number", sa.String(3), nullable=True),
        sa.Column("jv_type", sa.String(1), nullable=True),
        sa.Column("jv_number", sa.String(10), nullable=True),
        sa.Column("batch_number", sa.String, nullable=True),
        sa.Column("last_updated_on", sa.DateTime(), nullable=False),
        sa.Column("status_code", sa.String(length=20), nullable=False),
        sa.Column(
            "error_messages",
            postgresql.ARRAY(sa.String(150), dimensions=1),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["status_code"], ["eft_process_status_codes.code"]),
        sa.ForeignKeyConstraint(["file_id"], ["eft_files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("eft_transactions")
    op.drop_table("eft_files")
    op.drop_table("eft_process_status_codes")
