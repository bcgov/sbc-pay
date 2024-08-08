"""ppr_and_dissolution_filing_type_codes

Revision ID: 4cb0dc8e0013
Revises: f74980cff974
Create Date: 2021-10-06 07:57:39.021398

"""
from datetime import datetime, timezone

from alembic import op
from sqlalchemy import Date, String, text
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = '4cb0dc8e0013'
down_revision = '999f11310f30'
branch_labels = None
depends_on = None


def upgrade():
    distribution_code_link_table = table('distribution_code_links',
                                         column('distribution_code_id', String),
                                         column('fee_schedule_id', String)
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
                               column('service_fee_code', String),
                               column('future_effective_fee_code', String),
                               column('priority_fee_code', String)
                               )

    op.bulk_insert(
        filing_type_table,
        [
            {'code': 'SSRCH', 'description': 'Staff Search for Client'},
            {'code': 'DIS_VOL', 'description': 'Voluntary dissolution'},
            {'code': 'DIS_INVOL', 'description': 'Involuntary dissolution'},
            {'code': 'DIS_ADMIN', 'description': 'Administrative dissolution'},
            {'code': 'DIS_LQD', 'description': 'Voluntary liquidation'},
            {'code': 'DIS_COLQD', 'description': 'Court ordered liquidation'},
            {'code': 'DIS_RSTR', 'description': 'Dissolve a company that was restored in error'},
            {'code': 'AFDVT', 'description': 'Affidavit'},
            {'code': 'SPRLN', 'description': 'Special resolution'}
        ]
    )

    op.bulk_insert(
        fee_schedule_table,
        [
            {
                'filing_type_code': 'SSRCH',
                'corp_type_code': 'PPR',
                'fee_code': 'EN114',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'AFDVT',
                'corp_type_code': 'CP',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'SPRLN',
                'corp_type_code': 'CP',
                'fee_code': 'EN104',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_VOL',
                'corp_type_code': 'CP',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'DIS_LQD',
                'corp_type_code': 'CP',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'DIS_VOL',
                'corp_type_code': 'BC',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_INVOL',
                'corp_type_code': 'BC',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'DIS_ADMIN',
                'corp_type_code': 'BC',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'DIS_LQD',
                'corp_type_code': 'BC',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_COLQD',
                'corp_type_code': 'BC',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_RSTR',
                'corp_type_code': 'BC',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },

            {
                'filing_type_code': 'DIS_VOL',
                'corp_type_code': 'BEN',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_INVOL',
                'corp_type_code': 'BEN',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'DIS_ADMIN',
                'corp_type_code': 'BEN',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'DIS_LQD',
                'corp_type_code': 'BEN',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_COLQD',
                'corp_type_code': 'BEN',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_RSTR',
                'corp_type_code': 'BEN',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },

            {
                'filing_type_code': 'DIS_VOL',
                'corp_type_code': 'CC',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_INVOL',
                'corp_type_code': 'CC',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'DIS_ADMIN',
                'corp_type_code': 'CC',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'DIS_LQD',
                'corp_type_code': 'CC',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_COLQD',
                'corp_type_code': 'CC',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_RSTR',
                'corp_type_code': 'CC',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },

            {
                'filing_type_code': 'DIS_VOL',
                'corp_type_code': 'ULC',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_INVOL',
                'corp_type_code': 'ULC',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'DIS_ADMIN',
                'corp_type_code': 'ULC',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'DIS_LQD',
                'corp_type_code': 'ULC',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_COLQD',
                'corp_type_code': 'ULC',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_RSTR',
                'corp_type_code': 'ULC',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },

            {
                'filing_type_code': 'DIS_INVOL',
                'corp_type_code': 'LTD',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'DIS_ADMIN',
                'corp_type_code': 'LTD',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            },
            {
                'filing_type_code': 'DIS_LQD',
                'corp_type_code': 'LTD',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_COLQD',
                'corp_type_code': 'LTD',
                'fee_code': 'EN101',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': 'TRF01',
                'future_effective_fee_code': 'FUT01',
                'priority_fee_code': 'PRI01'
            },
            {
                'filing_type_code': 'DIS_RSTR',
                'corp_type_code': 'LTD',
                'fee_code': 'EN107',
                'fee_start_date': datetime.now(tz=timezone.utc),
                'fee_end_date': None,
                'service_fee_code': None,
                'future_effective_fee_code': None,
                'priority_fee_code': None
            }
        ]
    )

    # Now find out the distribution code for other SSRCH and map it to them.
    distribution_code_id_query = "select dc.distribution_code_id from distribution_codes dc " \
                                 "where upper(dc.name) = upper('PPR - Searches') " \
                                 "and dc.start_date <= CURRENT_DATE " \
                                 "and (dc.end_date is null or dc.end_date > CURRENT_DATE)"
    conn = op.get_bind()
    res = conn.execute(text(distribution_code_id_query))
    if (res_fetch := res.fetchall()) and res_fetch[0]:
        distribution_code_id = res_fetch[0][0]
        res = conn.execute(
            text(f"select fee_schedule_id from fee_schedules where corp_type_code='PPR' and filing_type_code='SSRCH'"))
        fee_schedule_id = res.fetchall()[0][0]
        distr_code_link = [{
            'distribution_code_id': distribution_code_id,
            'fee_schedule_id': fee_schedule_id
        }]
        op.bulk_insert(distribution_code_link_table, distr_code_link)

    # Now find out the distribution code for other SSRCH and map it to them.
    distribution_code_id_query = "select dc.distribution_code_id from distribution_codes dc " \
                                 "where upper(dc.name) = upper('Corporate Registry - Maintain Business') " \
                                 "and dc.start_date <= CURRENT_DATE " \
                                 "and (dc.end_date is null or dc.end_date > CURRENT_DATE)"
    conn = op.get_bind()
    res = conn.execute(text(distribution_code_id_query))
    if (res_fetch := res.fetchall()) and res_fetch[0]:
        distribution_code_id = res_fetch[0][0]
        res = conn.execute(
            text(f"select fee_schedule_id from fee_schedules where filing_type_code in ('DIS_VOL', 'DIS_INVOL', 'DIS_ADMIN', 'DIS_LQD', 'DIS_COLQD', 'DIS_RSTR', 'AFDVT', 'SPRLN')"))
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
        "DELETE FROM distribution_code_links WHERE fee_schedule_id in (select fee_schedule_id from fee_schedules where filing_type_code in ('SSRCH', 'DIS_VOL', 'DIS_INVOL', 'DIS_ADMIN', 'DIS_LQD', 'DIS_COLQD', 'DIS_RSTR', 'AFDVT', 'SPRLN'))")
    op.execute(
        "DELETE FROM fee_schedules WHERE filing_type_code in ('SSRCH', 'DIS_VOL', 'DIS_INVOL', 'DIS_ADMIN', 'DIS_LQD', 'DIS_COLQD', 'DIS_RSTR', 'AFDVT', 'SPRLN')")
    op.execute(
        "DELETE FROM filing_types WHERE code in ('SSRCH', 'DIS_VOL', 'DIS_INVOL', 'DIS_ADMIN', 'DIS_LQD', 'DIS_COLQD', 'DIS_RSTR', 'AFDVT', 'SPRLN')")
