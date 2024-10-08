"""adding_ppr_metadata

Revision ID: 5f7df60469fa
Revises: 4cc39da0bee7
Create Date: 2020-02-28 14:33:27.703812

"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Date, Float, String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = "5f7df60469fa"
down_revision = "4cc39da0bee7"
branch_labels = None
depends_on = None


def upgrade():
    payment_method_table = table(
        "payment_method", column("code", String), column("description", String)
    )

    op.bulk_insert(
        payment_method_table, [{"code": "DRAWDOWN", "description": "Drawdown Payment"}]
    )
    op.execute(
        "update payment set payment_method_code = 'DRAWDOWN' where payment_method_code='PREMIUM'"
    )
    op.execute("DELETE from payment_method where code='PREMIUM'")

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
        corp_type_table, [{"code": "PPR", "description": "Personal Property Registry"}]
    )
    op.bulk_insert(
        fee_code_table,
        [
            {"code": "EN110", "amount": 7},
            {"code": "EN111", "amount": 5},
            {"code": "EN112", "amount": 500},
        ],
    )
    op.bulk_insert(
        filing_type_table,
        [
            {"code": "SERCH", "description": "Search"},
            {"code": "FSREG", "description": "Yearly Financing Statement Registration"},
            {
                "code": "INFRG",
                "description": "Infinite Financing Statement Registration",
            },
        ],
    )
    op.bulk_insert(
        fee_schedule_table,
        [
            {
                "filing_type_code": "SERCH",
                "corp_type_code": "PPR",
                "fee_code": "EN110",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "FSREG",
                "corp_type_code": "PPR",
                "fee_code": "EN111",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
            {
                "filing_type_code": "INFRG",
                "corp_type_code": "PPR",
                "fee_code": "EN112",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
            },
        ],
    )


def downgrade():
    pass
