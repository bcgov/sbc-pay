import logging
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.db_connection import execute_query
from src.menu import auth_guard_with_redirect
from src.utils import display_report_with_download

logger = logging.getLogger(__name__)

report_title = "Basic Invoice Search Demo"

st.set_page_config(page_title=report_title, layout="wide", menu_items=None)

auth_guard_with_redirect()

st.title(report_title)

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    start_date_1 = st.date_input(
        "Payment Start",
        value=date.today() - timedelta(days=365),
        key="analytics_start1",
    )

with col2:
    end_date_1 = st.date_input(
        "Payment End", value=date.today(), key="analytics_end1"
    )

with col3:
    st.markdown("<br>", unsafe_allow_html=True)
    run_report = st.button("Run Report", key="run_report", type="primary")

if run_report:
    try:
        query = """
        select * from invoices
        where payment_date >= %s and payment_date <= %s
        order by id desc
        """

        results = execute_query(query, (start_date_1, end_date_1))
        st.session_state["basic_invoice_search_demo_report_df"] = (
            pd.DataFrame(results) if results else None
        )

    except Exception as e:
        logger.error("Query execution error: %s", str(e), exc_info=True)
        st.error(f"Error generating report: {str(e)}")
        st.session_state["basic_invoice_search_demo_report_df"] = None

if st.session_state.get("basic_invoice_search_demo_report_df") is not None:
    display_report_with_download(
        st.session_state["basic_invoice_search_demo_report_df"], report_title
    )
elif "basic_invoice_search_demo_report_df" in st.session_state:
    st.info("No data returned from query.")
