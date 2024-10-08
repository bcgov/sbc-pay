"""vital_statistics_fee_code

Revision ID: 06f6e75c18d8
Revises: a23093f25c56
Create Date: 2020-05-25 16:38:23.388619

"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "06f6e75c18d8"
down_revision = "a23093f25c56"
branch_labels = None
depends_on = None


def upgrade():
    corp_type_table = table(
        "corp_type", column("code", String), column("description", String)
    )
    fee_code_table = table("fee_code", column("code", String), column("amount", Float))
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

    # Product code/corp type
    op.bulk_insert(
        corp_type_table,
        [
            {
                "code": "VS",
                "description": "Vital Statistics",
                "transaction_fee_code": "TRF01",
            }
        ],
    )

    # Fee code, starting with EN201 as its a new product

    op.bulk_insert(
        fee_code_table,
        [
            {"code": "EN201", "amount": 17},
            {"code": "EN202", "amount": 20},
            {"code": "EN203", "amount": 5},
            {"code": "PRI02", "amount": 33},
        ],
    )

    # Filing Types
    op.bulk_insert(
        filing_type_table,
        [
            {"code": "WILLNOTICE", "description": "Wills Notice"},
            {"code": "WILLSEARCH", "description": "Wills Search"},
            {"code": "WILLALIAS", "description": "Wills Alias"},
        ],
    )

    # Fee Schedules
    op.bulk_insert(
        fee_schedule_table,
        [
            {
                "filing_type_code": "WILLNOTICE",
                "corp_type_code": "VS",
                "fee_code": "EN201",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
                "future_effective_fee_code": None,
                "priority_fee_code": "PRI02",
            },
            {
                "filing_type_code": "WILLSEARCH",
                "corp_type_code": "VS",
                "fee_code": "EN202",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
                "future_effective_fee_code": None,
                "priority_fee_code": "PRI02",
            },
            {
                "filing_type_code": "WILLALIAS",
                "corp_type_code": "VS",
                "fee_code": "EN203",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
                "future_effective_fee_code": None,
                "priority_fee_code": "PRI02",
            },
        ],
    )


def downgrade():
    op.execute(
        "delete from fee_schedule where filing_type_code in ('WILLNOTICE','WILLSEARCH','WILLALIAS') "
    )
    op.execute(
        "delete from filing_type where code in ('WILLNOTICE','WILLSEARCH','WILLALIAS') "
    )
    op.execute("delete from fee_code where code in ('EN201','EN202','EN203', 'PRI02') ")
    op.execute("delete from corp_type where code in ('VS') ")
