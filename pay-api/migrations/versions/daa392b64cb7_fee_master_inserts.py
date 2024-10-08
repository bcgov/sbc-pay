"""fee_master_inserts

Revision ID: daa392b64cb7
Revises: 55f71addab9d
Create Date: 2019-05-10 11:07:41.003718

"""

from datetime import datetime, timezone

from alembic import op
from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "daa392b64cb7"
down_revision = "55f71addab9d"
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

    op.bulk_insert(corp_type_table, [{"code": "CP", "description": "Cooperative"}])
    op.bulk_insert(
        fee_code_table,
        [
            {"code": "EN101", "amount": 20},
            {"code": "EN102", "amount": 25},
            {"code": "EN103", "amount": 30},
            {"code": "EN104", "amount": 70},
            {"code": "EN105", "amount": 100},
            {"code": "EN106", "amount": 250},
            {"code": "EN107", "amount": 0},
        ],
    )
    op.bulk_insert(
        filing_type_table,
        [
            {"code": "OTANN", "description": "Annual Report"},
            {"code": "OTADD", "description": "Change of Registered Office Address"},
            {"code": "OTCDR", "description": "Change of Director"},
            {"code": "OTSPE", "description": "Resolution"},
            {"code": "OTINC", "description": "Incorporation"},
            {"code": "OTREG", "description": "Registration"},
            {"code": "OTRES", "description": "Restoration Application"},
            {"code": "OTAMR", "description": "Amended Annual Report"},
            {"code": "OTADR", "description": "Amended Change of Director"},
            {"code": "OTCGM", "description": "Change of AGM Date and/or Location"},
            {"code": "OTAMA", "description": "Amalgamation"},
        ],
    )
    op.bulk_insert(
        fee_schedule_table,
        [
            {
                "filing_type_code": "OTANN",
                "corp_type_code": "CP",
                "fee_code": "EN103",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTADD",
                "corp_type_code": "CP",
                "fee_code": "EN101",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTCDR",
                "corp_type_code": "CP",
                "fee_code": "EN101",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTSPE",
                "corp_type_code": "CP",
                "fee_code": "EN104",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTINC",
                "corp_type_code": "CP",
                "fee_code": "EN106",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTAMA",
                "corp_type_code": "CP",
                "fee_code": "EN106",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTREG",
                "corp_type_code": "CP",
                "fee_code": "EN106",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTRES",
                "corp_type_code": "CP",
                "fee_code": "EN106",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTAMR",
                "corp_type_code": "CP",
                "fee_code": "EN101",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTADR",
                "corp_type_code": "CP",
                "fee_code": "EN101",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "OTCGM",
                "corp_type_code": "CP",
                "fee_code": "EN107",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
        ],
    )


def downgrade():
    pass
