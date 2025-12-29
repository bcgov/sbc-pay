from datetime import date, datetime

import pandas as pd
import streamlit as st

from src.db_connection import execute_query
from src.menu import auth_guard_with_redirect

st.set_page_config(
    page_title="STRR Revenue Report", layout="wide", menu_items=None
)

auth_guard_with_redirect()

st.title("STRR Revenue Report")

report_title = "STRR Revenue Report"

col1, col2, spacer = st.columns([0.8, 0.8, 10])

with col1:
    start_date_1 = st.date_input(
        "Report Start", value=date.today(), key="analytics_start1"
    )

with col2:
    end_date_1 = st.date_input(
        "Report End", value=date.today(), key="analytics_end1"
    )

try:
    query = """
        WITH completed AS (
            SELECT
                disbursement_date::date AS date,
                SUM(total - service_fees) AS sbc_pay_total_disbursed
            FROM invoices
            WHERE corp_type_code = 'STRR'
            AND disbursement_status_code IN ('COMPLETED', 'REVERSED')
            GROUP BY disbursement_date::date
        ),
        reversed AS (
            SELECT
                disbursement_reversal_date::date AS date,
                SUM(total - service_fees) AS sbc_pay_total_reversed
            FROM invoices
            WHERE corp_type_code = 'STRR'
            AND disbursement_status_code = 'REVERSED'
            GROUP BY disbursement_reversal_date::date
        ),
        partial_rev AS (
            SELECT
                pd.feedback_on::date AS date,
                SUM(rp.refund_amount) AS sbc_pay_total_partial_reversed
            FROM refunds_partial rp
            JOIN partner_disbursements pd
            ON pd.target_id = rp.id
            AND pd.target_type = 'partial_refund'
            WHERE rp.invoice_id IN (
                SELECT id
                FROM invoices
                WHERE corp_type_code = 'STRR'
            )
            GROUP BY pd.feedback_on::date
        ),
        revenue_paid AS (
            SELECT
                payment_date::date AS date,
                SUM(total - service_fees) AS sbc_revenue_paid
            FROM invoices
            WHERE corp_type_code = 'STRR'
            AND payment_date IS NOT NULL
            GROUP BY payment_date::date
        ),
        revenue_reversed AS (
            SELECT
                refund_date::date AS date,
                SUM(refund - service_fees) AS sbc_revenue_reversed
            FROM invoices
            WHERE corp_type_code = 'STRR'
            AND refund_date IS NOT NULL
            GROUP BY refund_date::date
        ),

        cas AS (
            SELECT
                effective_date::date AS date,
                SUM(je_lines_dr_amount) AS cas_dr_amount,
                SUM(je_lines_cr_amount) AS cas_cr_amount
            FROM cas.gl_je_lines
            WHERE client = '112'
            AND responsibility = '32338'
            AND service_line = '34725'
            AND stob = '3000'
            AND project = '3200440'
            AND je_line_description ILIKE '%DISBURSEMENTS%'
            GROUP BY effective_date::date
        ),
        dates AS (
            SELECT date FROM completed
            UNION
            SELECT date FROM reversed
            UNION
            SELECT date FROM partial_rev
            UNION
            SELECT date FROM revenue_paid
            UNION
            SELECT date FROM revenue_reversed
            UNION
            SELECT date FROM cas
        )
        SELECT
            d.date,

            COALESCE(rp.sbc_revenue_paid, 0)     AS sbc_revenue_paid,
            COALESCE(rr.sbc_revenue_reversed, 0) AS sbc_revenue_reversed,
            COALESCE(rp.sbc_revenue_paid, 0) - COALESCE(rr.sbc_revenue_reversed, 0) AS sbc_revenue_net,
            COALESCE(c.sbc_pay_total_disbursed, 0) AS sbc_pay_total_disbursed,
            COALESCE(r.sbc_pay_total_reversed, 0) AS sbc_pay_total_reversed,
            COALESCE(p.sbc_pay_total_partial_reversed, 0) AS sbc_pay_total_partial_reversed,

            COALESCE(c.sbc_pay_total_disbursed, 0)
            - COALESCE(r.sbc_pay_total_reversed, 0)
            - COALESCE(p.sbc_pay_total_partial_reversed, 0)
            AS sbc_pay_net,

            COALESCE(cas.cas_dr_amount, 0) AS cas_dr_amount,
            COALESCE(cas.cas_cr_amount, 0) AS cas_cr_amount,
            COALESCE(cas.cas_dr_amount, 0)
            - COALESCE(cas.cas_cr_amount, 0)
            AS cas_net,

            (
                COALESCE(c.sbc_pay_total_disbursed, 0)
                - COALESCE(r.sbc_pay_total_reversed, 0)
                - COALESCE(p.sbc_pay_total_partial_reversed, 0)
            )
            - (
                COALESCE(cas.cas_dr_amount, 0)
                - COALESCE(cas.cas_cr_amount, 0)
            ) AS sbc_pay_cas_difference

        FROM dates d
        LEFT JOIN completed c         ON c.date = d.date
        LEFT JOIN reversed r          ON r.date = d.date
        LEFT JOIN partial_rev p       ON p.date = d.date
        LEFT JOIN revenue_paid rp     ON rp.date = d.date
        LEFT JOIN revenue_reversed rr ON rr.date = d.date
        LEFT JOIN cas                 ON cas.date = d.date
        WHERE d.date >= %s AND d.date <= %s
        ORDER BY d.date;
    """

    results = execute_query(query, (start_date_1, end_date_1))

    if results:
        df = pd.DataFrame(results)
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            key="download_analytics",
        )
        st.dataframe(df)
    else:
        st.info("No data returned from query.")

except Exception as e:
    st.error(f"Error generating report: {str(e)}")
