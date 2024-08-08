"""restricted ppr fee codes

Revision ID: 9c8a93ba9da2
Revises: 0aa7d4deef8a
Create Date: 2021-06-04 08:27:25.551857

"""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Date, Float, String, Boolean
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = '9c8a93ba9da2'
down_revision = '0aa7d4deef8a'
branch_labels = None
depends_on = None


def upgrade():
    # corp type, filing type, fee schedule

    corp_type_table = table('corp_types',
                            column('code', String),
                            column('description', String),
                            column('product', String),
                            column('is_online_banking_allowed', Boolean)
                            )
    filing_type_table = table('filing_types',
                              column('code', String),
                              column('description', String)
                              )
    fee_schedule_table = table('fee_schedules',
                               column('filing_type_code', String),
                               column('corp_type_code', String),
                               column('fee_code', String),
                               column('fee_start_date', Date),
                               column('fee_end_date', Date)
                               )

    op.bulk_insert(
        corp_type_table,
        [
            {'code': 'RPPR', 'description': 'Restricted Personal Property Registry',
             'product': 'RPPR', 'is_online_banking_allowed': True}
        ]
    )

    op.bulk_insert(
        filing_type_table,
        [
            {'code': 'MAREG', 'description': 'PPR Crown/Misc Act Registration'}
        ]
    )

    op.bulk_insert(
        fee_schedule_table,
        [
            {'filing_type_code': 'MAREG', 'corp_type_code': 'RPPR', 'fee_code': 'EN107', 'fee_start_date': datetime.now(tz=timezone.utc),
             'fee_end_date': None},
        ]
    )


def downgrade():
    op.execute("DELETE FROM fee_schedules WHERE filing_type_code in ('MAREG')")
    op.execute("DELETE FROM filing_types WHERE code in ('MAREG')")
    op.execute("DELETE FROM corp_types WHERE code in ('RPPR')")
