"""Menu configuration for authenticated and unauthenticated users."""

import streamlit as st


def authenticated_menu():
    """Build sidebar menu for authenticated users."""
    # We can expand this in the future to hide or show pages based on roles.
    with st.sidebar:
        st.page_link("app.py", label="Home", icon="🏠")
        st.page_link(
            "pages/Basic Invoice Search Demo.py",
            label="Basic Invoice Search Demo",
            icon="📊",
        )


def unauthenticated_menu():
    """Trigger login for unauthenticated users."""
    st.login()
    st.stop()


def auth_guard_with_redirect():
    """
    Build sidebar and redirect if not authenticated.

    This function checks authentication status and redirects to the login
    page if the user is not authenticated. Otherwise, it displays the
    authenticated menu.
    """
    if not st.user.is_logged_in:
        st.switch_page("app.py")
    authenticated_menu()
