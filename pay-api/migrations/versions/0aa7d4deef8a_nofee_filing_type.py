"""nofee_filing_type

Revision ID: 0aa7d4deef8a
Revises: 7b8f813d7a14
Create Date: 2021-05-17 13:15:02.260765

"""

from datetime import datetime, timezone

from alembic import op
from sqlalchemy import Date, String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "0aa7d4deef8a"
down_revision = "7b8f813d7a14"
branch_labels = None
depends_on = None


def upgrade():
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
        column("future_effective_fee_code", String),
        column("priority_fee_code", String),
    )

    # Filing Types
    op.bulk_insert(
        filing_type_table, [{"code": "NOFEE", "description": "No Fee Staff Filing"}]
    )

    op.bulk_insert(
        fee_schedule_table,
        [
            {
                "filing_type_code": "NOFEE",
                "corp_type_code": "BC",
                "fee_code": "EN107",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
                "future_effective_fee_code": None,
                "priority_fee_code": None,
            },
            {
                "filing_type_code": "NOFEE",
                "corp_type_code": "CP",
                "fee_code": "EN107",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
                "future_effective_fee_code": None,
                "priority_fee_code": None,
            },
            {
                "filing_type_code": "NOFEE",
                "corp_type_code": "BEN",
                "fee_code": "EN107",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
                "future_effective_fee_code": None,
                "priority_fee_code": None,
            },
            {
                "filing_type_code": "NOFEE",
                "corp_type_code": "ULC",
                "fee_code": "EN107",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
                "future_effective_fee_code": None,
                "priority_fee_code": None,
            },
        ],
    )


def downgrade():
    op.execute("delete from fee_schedules where filing_type_code='NOFEE'")
    op.execute("delete from filing_types where code='NOFEE'")
