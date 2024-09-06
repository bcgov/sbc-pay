"""correction_fee_codes

Revision ID: 5cdd1c1d355e
Revises: ac01134753e9
Create Date: 2020-02-13 13:43:53.035222

"""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = '5cdd1c1d355e'
down_revision = 'ac01134753e9'
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
        column("priority_fee_code", String)
    )

    # Filing Types
    op.bulk_insert(
        filing_type_table,
        [
            {'code': 'CRCTN', 'description': 'Correction'}
        ]
    )

    # Fee Schedules
    op.bulk_insert(
        fee_schedule_table,
        [
            {
                "filing_type_code": "CRCTN",
                "corp_type_code": "BC",
                "fee_code": "EN101",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
                "future_effective_fee_code": None,
                "priority_fee_code": "PRI01",
            },
            {
                "filing_type_code": "CRCTN",
                "corp_type_code": "CP",
                "fee_code": "EN101",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
                "future_effective_fee_code": None,
                "priority_fee_code": "PRI01",
            }
        ],
    )

def downgrade():
    # Delete the records
    op.execute('DELETE FROM fee_schedule where filing_type_code=\'CRCTN\'')
    op.execute("DELETE FROM filing_type where code = 'CRCTN'")
