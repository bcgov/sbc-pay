"""Main Streamlit application entry point."""

import streamlit as st

from src.auth import get_username
from src.menu import authenticated_menu, unauthenticated_menu

st.set_page_config(
    page_title="Pay Team Report Dashboard",
    layout="wide",
    menu_items=None,
)

# Build sidebar navigation based on auth status
if st.user.is_logged_in:
    authenticated_menu()
else:
    unauthenticated_menu()

st.title("Pay Team Report Dashboard")

st.subheader(f"Welcome, {get_username()}!")

st.markdown("""
### Welcome to the Pay Team Report Dashboard

**Access Requirements:**
- Authentication via Keycloak is required
- Users must have the `pay-report` role assigned
""")

st.markdown("""
---

*For questions or support, please contact Pay Team.*
""")
