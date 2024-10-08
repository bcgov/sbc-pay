"""alteration_filing

Revision ID: 7ea7ba8fe991
Revises: cf9a60955b68
Create Date: 2020-07-27 16:45:41.623672

"""

from datetime import datetime, timezone

from alembic import op
from sqlalchemy import Date, String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "7ea7ba8fe991"
down_revision = "cf9a60955b68"
branch_labels = None
depends_on = None


def upgrade():
    filing_type_table = table(
        "filing_type", column("code", String), column("description", String)
    )

    fee_schedule_table = table(
        "fee_schedule",
        column("filing_type_code", String),
        column("corp_type_code", String),
        column("fee_code", String),
        column("fee_start_date", Date),
        column("fee_end_date", Date),
        column("future_effective_fee_code", String),
        column("priority_fee_code", String),
    )

    payment_method_table = table(
        "payment_method", column("code", String), column("description", String)
    )

    # Filing Types
    op.bulk_insert(filing_type_table, [{"code": "ALTER", "description": "Alteration"}])

    # Fee Schedules
    op.bulk_insert(
        fee_schedule_table,
        [
            {
                "filing_type_code": "ALTER",
                "corp_type_code": "BC",
                "fee_code": "EN105",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
                "future_effective_fee_code": "FUT01",
                "priority_fee_code": "PRI01",
            }
        ],
    )

    # INTERNAL Payment method
    op.bulk_insert(
        payment_method_table, [{"code": "INTERNAL", "description": "Staff Payment"}]
    )


def downgrade():
    # Delete the records
    op.execute("DELETE FROM fee_schedule where filing_type_code='ALTER'")
    op.execute("DELETE FROM filing_type where code = 'ALTER'")
    op.execute("DELETE FROM payment_method where code = 'INTERNAL'")
