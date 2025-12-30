"""Utility functions for report pages."""

from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st


def display_report_with_download(df, report_title):
    """Display DataFrame and provide XLSX download button."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Report")
    output.seek(0)
    file_name = (
        f"{report_title.replace(' ', '_')}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )
    mime_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.download_button(
        label="Download XLSX",
        data=output,
        file_name=file_name,
        mime=mime_type,
        key="download_analytics",
    )
    st.dataframe(df)
