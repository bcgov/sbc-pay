"""fee_master_for_BCORPS

Revision ID: e6eb14b9d50e
Revises: 4a6ddf932b62
Create Date: 2019-10-29 10:44:55.220375

"""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "e6eb14b9d50e"
down_revision = "4a6ddf932b62"
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
    )

    op.bulk_insert(
        corp_type_table, [{"code": "BC", "description": "Benefit Corporations"}]
    )
    op.bulk_insert(fee_code_table, [{"code": "EN108", "amount": 43.39}])
    op.bulk_insert(
        fee_schedule_table,
        [
            {
                "filing_type_code": "OTANN",
                "corp_type_code": "BC",
                "fee_code": "EN108",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTADD",
                "corp_type_code": "BC",
                "fee_code": "EN101",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTCDR",
                "corp_type_code": "BC",
                "fee_code": "EN101",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTSPE",
                "corp_type_code": "BC",
                "fee_code": "EN104",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTINC",
                "corp_type_code": "BC",
                "fee_code": "EN106",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTAMA",
                "corp_type_code": "BC",
                "fee_code": "EN106",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTREG",
                "corp_type_code": "BC",
                "fee_code": "EN106",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTRES",
                "corp_type_code": "BC",
                "fee_code": "EN106",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTAMR",
                "corp_type_code": "BC",
                "fee_code": "EN101",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTADR",
                "corp_type_code": "BC",
                "fee_code": "EN101",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTCGM",
                "corp_type_code": "BC",
                "fee_code": "EN107",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTFDR",
                "corp_type_code": "BC",
                "fee_code": "EN107",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
        ],
    )


def downgrade():
    pass
