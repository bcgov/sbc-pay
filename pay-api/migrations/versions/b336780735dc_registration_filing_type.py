"""registration_filing_type

Revision ID: b336780735dc
Revises: 5d9997f7e649
Create Date: 2021-11-30 09:33:57.641970

"""
from datetime import date

from alembic import op
from sqlalchemy import Date, String, Boolean, Float, text
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = 'b336780735dc'
down_revision = '5d9997f7e649'
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
                            column('is_online_banking_allowed', Boolean),
                            column('bcol_fee_code', String),
                            column('bcol_staff_fee_code', String),
                            )
    filing_type_table = table('filing_types',
                              column('code', String),
                              column('description', String)
                              )
    fee_codes_table = table('fee_codes',
                            column('code', String),
                            column('amount', Float)
                            )
    fee_schedule_table = table('fee_schedules',
                               column('filing_type_code', String),
                               column('corp_type_code', String),
                               column('fee_code', String),
                               column('fee_start_date', Date),
                               column('fee_end_date', Date),
                               column('service_fee_code', String),
                               column('priority_fee_code', String)
                               )

    op.bulk_insert(
        corp_type_table,
        [
            {
                'code': 'SP',
                'description': 'Sole Proprietorship',
                'product': 'BUSINESS',
                'is_online_banking_allowed': True,
                'bcol_fee_code': 'BBCOMVC1',
                'bcol_staff_fee_code': 'CBCOMVC1'
            },
            {
                'code': 'GP',
                'description': 'General Partnership',
                'product': 'BUSINESS',
                'is_online_banking_allowed': True,
                'bcol_fee_code': 'BBCOMVC1',
                'bcol_staff_fee_code': 'CBCOMVC1'
            }
        ]
    )

    op.bulk_insert(
        fee_codes_table,
        [
            {
                'code': 'EN116',
                'amount': 40
            }
        ]
    )

    op.bulk_insert(
        filing_type_table,
        [
            {'code': 'FRREG', 'description': 'Statement of Registration'}
        ]
    )

    op.bulk_insert(
        fee_schedule_table,
        [
            {
                'filing_type_code': 'FRREG',
                'corp_type_code': 'SP',
                'fee_code': 'EN116',
                'fee_start_date': date.today(),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'FRREG',
                'corp_type_code': 'GP',
                'fee_code': 'EN116',
                'fee_start_date': date.today(),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'priority_fee_code': 'PRI01'
            }
        ]
    )

    # Now find out the distribution code for other FRREG and map it to them.
    distribution_code_id_query = "select dc.distribution_code_id from distribution_codes dc " \
                                 "where upper(dc.name) = upper('Corporate Registry - Form a Business') " \
                                 "and dc.start_date <= CURRENT_DATE " \
                                 "and (dc.end_date is null or dc.end_date > CURRENT_DATE)"
    conn = op.get_bind()
    res = conn.execute(text(distribution_code_id_query))
    if (res_fetch := res.fetchall()) and res_fetch[0]:
        distribution_code_id = res_fetch[0][0]
        res = conn.execute(
            text("select fee_schedule_id from fee_schedules where filing_type_code = 'FRREG'"))

        distr_code_links = []
        for result in res.fetchall():
            fee_schedule_id = result[0]
            distr_code_links.append({
                'distribution_code_id': distribution_code_id,
                'fee_schedule_id': fee_schedule_id
            })
        op.bulk_insert(distribution_code_link_table, distr_code_links)


def downgrade():
    op.execute(
        "DELETE FROM distribution_code_links WHERE fee_schedule_id in (select fee_schedule_id from fee_schedules where "
        "filing_type_code = 'FRREG')")
    op.execute("DELETE FROM fee_schedules WHERE filing_type_code = 'FRREG'")
    op.execute("DELETE FROM filing_types WHERE code = 'FRREG'")
    op.execute("DELETE FROM fee_codes WHERE code = 'EN116'")
    op.execute("DELETE FROM corp_types WHERE code in ('SP', 'GP')")
