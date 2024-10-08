"""ppr_filing_types

Revision ID: 44bd57ece7b0
Revises: 609b98d87a72
Create Date: 2021-09-16 16:25:58.618648

"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Date, Float, String, Boolean
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = "44bd57ece7b0"
down_revision = "609b98d87a72"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        op.f("ix_invoices_created_on"), "invoices", ["created_on"], unique=False
    )
    op.alter_column(
        "payment_line_items",
        "fee_distribution_id",
        existing_type=sa.INTEGER(),
        nullable=True,
    )

    filing_type_table = table(
        "filing_types", column("code", String), column("description", String)
    )
    fee_schedule_table = table(
        "fee_schedules",
        column("filing_type_code", String),
        column("corp_type_code", String),
        column("fee_code", String),
        column("fee_start_date", Date),
        column("fee_end_date", Date),
    )

    op.bulk_insert(
        filing_type_table,
        [
            {"code": "FSDIS", "description": "PPR Total Discharge"},
            {"code": "NCREG", "description": "PPR No Charge Registration"},
            {"code": "NCCHG", "description": "PPR No Charge Change or Amendment"},
        ],
    )

    op.bulk_insert(
        fee_schedule_table,
        [
            {
                "filing_type_code": "FSDIS",
                "corp_type_code": "PPR",
                "fee_code": "EN107",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "NCREG",
                "corp_type_code": "PPR",
                "fee_code": "EN107",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "NCCHG",
                "corp_type_code": "PPR",
                "fee_code": "EN107",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
        ],
    )


def downgrade():
    op.execute(
        "DELETE FROM fee_schedules WHERE filing_type_code in ('NCCHG', 'NCREG', 'FSDIS')"
    )
    op.execute("DELETE FROM filing_types WHERE code in ('NCCHG', 'NCREG', 'FSDIS')")
    op.alter_column(
        "payment_line_items",
        "fee_distribution_id",
        existing_type=sa.INTEGER(),
        nullable=False,
    )
    op.drop_index(op.f("ix_invoices_created_on"), table_name="invoices")
