"""adding_ppr_metadata

Revision ID: 5f7df60469fa
Revises: 4cc39da0bee7
Create Date: 2020-02-28 14:33:27.703812

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import column, table
from sqlalchemy import String, Date, Float
from datetime import date


# revision identifiers, used by Alembic.
revision = '5f7df60469fa'
down_revision = '4cc39da0bee7'
branch_labels = None
depends_on = None


def upgrade():
    corp_type_table = table('corp_type',
                            column('code', String),
                            column('description', String)
                            )
    fee_code_table = table('fee_code',
                           column('code', String),
                           column('amount', Float)
                           )
    filing_type_table = table('filing_type',
                              column('code', String),
                              column('description', String)
                              )
    fee_schedule_table = table('fee_schedule',
                               column('filing_type_code', String),
                               column('corp_type_code', String),
                               column('fee_code', String),
                               column('fee_start_date', Date),
                               column('fee_end_date', Date)
                               )

    op.bulk_insert(
        corp_type_table,
        [
            {'code': 'PPR', 'description': 'Personal Property Registry'}
        ]
    )
    op.bulk_insert(
        fee_code_table,
        [
            {'code': 'EN110', 'amount': 7}
        ]
    )
    op.bulk_insert(
        filing_type_table,
        [
            {'code': 'SERCH', 'description': 'Search'}
        ]
    )
    op.bulk_insert(
        fee_schedule_table,
        [
            {'filing_type_code': 'SERCH', 'corp_type_code': 'PPR', 'fee_code': 'EN110', 'fee_start_date': date.today(),
             'fee_end_date': None}
        ]
    )


def downgrade():
    pass
