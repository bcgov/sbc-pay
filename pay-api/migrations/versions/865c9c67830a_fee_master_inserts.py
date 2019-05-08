"""fee_master_inserts

Revision ID: 865c9c67830a
Revises: 0328c7f2abbc
Create Date: 2019-05-07 11:43:13.598460

"""
from datetime import date

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Date, Integer, String
from sqlalchemy.sql import column, table


# revision identifiers, used by Alembic.
revision = '865c9c67830a'
down_revision = '0328c7f2abbc'
branch_labels = None
depends_on = None


def upgrade():
    corp_type_table = table('corp_type',
                            column('corp_type_code', String),
                            column('corp_type_description', String)
                            )
    fee_code_table = table('fee_code',
                            column('fee_code', String),
                            column('amount', Integer)
                            )
    filing_type_table = table('filing_type',
                            column('filing_type_code', String),
                            column('filing_description', String)
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
            {'corp_type_code': 'CP', 'corp_type_description': 'Cooperative'}
        ]
    )
    op.bulk_insert(
        fee_code_table,
        [
            {'fee_code': 'EN101', 'amount': 20},
            {'fee_code': 'EN102', 'amount': 25},
            {'fee_code': 'EN103', 'amount': 30},
            {'fee_code': 'EN104', 'amount': 70},
            {'fee_code': 'EN105', 'amount': 100},
            {'fee_code': 'EN106', 'amount': 250},
            {'fee_code': 'EN107', 'amount': 0}
        ]
    )
    op.bulk_insert(
        filing_type_table,
        [
            {'filing_type_code': 'OTANN', 'filing_description':'Annual Report'},
            {'filing_type_code': 'OTADD', 'filing_description': 'Change of Registered Office Address'},
            {'filing_type_code': 'OTCDR', 'filing_description': 'Change of Director'},
            {'filing_type_code': 'OTSPE', 'filing_description': 'Resolution'},
            {'filing_type_code': 'OTINC', 'filing_description': 'Incorporation'},
            {'filing_type_code': 'OTREG', 'filing_description': 'Registration'},
            {'filing_type_code': 'OTRES', 'filing_description': 'Restoration Application'},
            {'filing_type_code': 'OTAMR', 'filing_description': 'Amended Annual Report'},
            {'filing_type_code': 'OTADR', 'filing_description': 'Amended Change of Director'},
            {'filing_type_code': 'OTCGM', 'filing_description': 'Change of AGM Date and/or Location'},
            {'filing_type_code': 'OTAMA', 'filing_description': 'Amalgamation'}
        ]
    )
    op.bulk_insert(
        fee_schedule_table,
        [
            {'filing_type_code':'OTANN', 'corp_type_code':'CP', 'fee_code':'EN103', 'fee_start_date': date.today(),
             'fee_end_date':None},
            {'filing_type_code': 'OTADD', 'corp_type_code': 'CP', 'fee_code': 'EN101', 'fee_start_date': date.today(),
             'fee_end_date': None},
            {'filing_type_code': 'OTCDR', 'corp_type_code': 'CP', 'fee_code': 'EN101', 'fee_start_date': date.today(),
             'fee_end_date': None},
            {'filing_type_code': 'OTSPE', 'corp_type_code': 'CP', 'fee_code': 'EN104', 'fee_start_date': date.today(),
             'fee_end_date': None},
            {'filing_type_code': 'OTINC', 'corp_type_code': 'CP', 'fee_code': 'EN106', 'fee_start_date': date.today(),
             'fee_end_date': None},
            {'filing_type_code': 'OTAMA', 'corp_type_code': 'CP', 'fee_code': 'EN106', 'fee_start_date': date.today(),
             'fee_end_date': None},
            {'filing_type_code': 'OTREG', 'corp_type_code': 'CP', 'fee_code': 'EN106', 'fee_start_date': date.today(),
             'fee_end_date': None},
            {'filing_type_code': 'OTRES', 'corp_type_code': 'CP', 'fee_code': 'EN106', 'fee_start_date': date.today(),
             'fee_end_date': None},
            {'filing_type_code': 'OTAMR', 'corp_type_code': 'CP', 'fee_code': 'EN101', 'fee_start_date': date.today(),
             'fee_end_date': None},
            {'filing_type_code': 'OTADR', 'corp_type_code': 'CP', 'fee_code': 'EN101', 'fee_start_date': date.today(),
             'fee_end_date': None},
            {'filing_type_code': 'OTCGM', 'corp_type_code': 'CP', 'fee_code': 'EN107', 'fee_start_date': date.today(),
             'fee_end_date': None}
        ]
    )


def downgrade():
    pass
