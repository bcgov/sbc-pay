"""rpt

Revision ID: 609b98d87a72
Revises: 9543cbcb8b79
Create Date: 2021-09-16 11:09:04.691660

"""
from datetime import date

from alembic import op
from sqlalchemy import Date, String, Boolean, text
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = '609b98d87a72'
down_revision = '9543cbcb8b79'
branch_labels = None
depends_on = None


def upgrade():
    distribution_code_link_table = table('distribution_code_links',
                                         column('distribution_code_id', String),
                                         column('fee_schedule_id', String)
                                         )
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
                               column('fee_end_date', Date),
                               column('service_fee_code', String)
                               )

    op.bulk_insert(
        corp_type_table,
        [
            {'code': 'RPT', 'description': 'Rural Property Tax',
             'product': 'RPT', 'is_online_banking_allowed': False}
        ]
    )

    op.bulk_insert(
        filing_type_table,
        [
            {'code': 'OLLXTFI', 'description': 'Rural Property Tax Certificate'}
        ]
    )

    op.bulk_insert(
        fee_schedule_table,
        [
            {
                'filing_type_code': 'OLLXTFI',
                'corp_type_code': 'RPT',
                'fee_code': 'EN111',
                'fee_start_date': date.today(),
                'fee_end_date': None,
                'service_fee_code': 'TRF01'
            }
        ]
    )

    # Now find out the distribution code for other BCINC and map it to them.
    distribution_code_id_query = "select dc.distribution_code_id from distribution_codes dc " \
                                 "where upper(dc.name) = upper('Rural Property E-tax Search') " \
                                 "and dc.start_date <= CURRENT_DATE " \
                                 "and (dc.end_date is null or dc.end_date > CURRENT_DATE)"
    conn = op.get_bind()
    res = conn.execute(text(distribution_code_id_query))
    if (res_fetch := res.fetchall()) and res_fetch[0]:
        distribution_code_id = res_fetch[0][0]
        res = conn.execute(
            text(f"select fee_schedule_id from fee_schedules where corp_type_code='RPT' and filing_type_code='OLLXTFI'"))
        fee_schedule_id = res.fetchall()[0][0]
        distr_code_link = [{
            'distribution_code_id': distribution_code_id,
            'fee_schedule_id': fee_schedule_id
        }]
        op.bulk_insert(distribution_code_link_table, distr_code_link)


def downgrade():
    op.execute(
        "DELETE FROM distribution_code_links WHERE fee_schedule_id in (select fee_schedule_id from fee_schedules where filing_type_code='OLLXTFI')")
    op.execute("DELETE FROM fee_schedules WHERE filing_type_code in ('OLLXTFI')")
    op.execute("DELETE FROM filing_types WHERE code in ('OLLXTFI')")
    op.execute("DELETE FROM corp_types WHERE code in ('RPT')")
