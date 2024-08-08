"""NR_fee_codes

Revision ID: e8edc889072d
Revises: 17b404b3df45
Create Date: 2020-06-23 11:06:16.156584

"""
from datetime import datetime, timezone

from alembic import op
from sqlalchemy import Date, Float, String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = 'e8edc889072d'
down_revision = '17b404b3df45'
branch_labels = None
depends_on = None


def upgrade():
    corp_type_table = table(
        "corp_type",
        column("code", String),
        column("description", String),
        column("service_fee_code", String),
        column("bcol_fee_code", String),
        column("gl_memo", String),
        column("service_gl_memo", String)
    )

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

    # Corp Type
    op.bulk_insert(
        corp_type_table, [{
            "code": "NRO",
            "description": "Name Requests Online",
            "service_fee_code": "TRF01",
            "bcol_fee_code": None,
            "gl_memo": "Benefit Companies",
            "service_gl_memo": "SBC Modernization Service Charge"
        }]
    )

    # Filing Types
    op.bulk_insert(
        filing_type_table,
        [
            {'code': 'NM620', 'description': 'Reg. Submission Online'},
            {'code': 'NM606', 'description': 'Upgrade to Priority'}

        ]
    )

    # Fee Schedule
    op.bulk_insert(
        fee_schedule_table,
        [
            {
                "filing_type_code": "NM620",
                "corp_type_code": "NRO",
                "fee_code": "EN103",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
                "future_effective_fee_code": None,
                "priority_fee_code": "PRI01"
            },
            {
                "filing_type_code": "NM606",
                "corp_type_code": "NRO",
                "fee_code": "EN105",
                "fee_start_date": datetime.now(tz=timezone.utc),
                "fee_end_date": None,
                "future_effective_fee_code": None,
                "priority_fee_code": None
            }
        ]
    )


def downgrade():
    op.execute("delete from fee_schedule where corp_type_code='NRO'")
    op.execute("delete from filing_type where code in ('NM620', 'NM606')")
    op.execute("delete from corp_type where code='NRO')")
