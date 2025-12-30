"""Authentication module using Streamlit native auth."""

from functools import wraps

import streamlit as st


class AccessDeniedError(Exception):
    """Raised when user lacks required role for access."""


def enforce_auth():
    """
    Enforce authentication on every page load.

    This runs automatically when the module is imported.
    Checks authentication status and required role, stops execution if not
    authenticated or missing role.
    This also should run before getting a database connection.
    """
    if not st.user.is_logged_in:
        st.login()
        st.stop()

    user_info = st.user
    required_role = "pay-report"
    roles = user_info.get("roles", [])
    if required_role not in roles:
        st.error(f"Access denied. Required role: {required_role}.")
        st.stop()
        raise AccessDeniedError(  # noqa: B904
            f"Access denied. Required role: {required_role}."
        )


def require_keycloak_auth(func):
    """
    Decorator to enforce Keycloak authentication before function execution.

    Wraps a function to ensure the user is authenticated and has the
    required role before the function is called.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        enforce_auth()
        return func(*args, **kwargs)

    return wrapper


def get_username():
    """
    Get the username from the authenticated user info.

    Returns the user's name or preferred username.
    """
    if not st.user.is_logged_in:
        return "User"

    user_info = st.user
    return (
        user_info.get("name") or user_info.get("preferred_username") or "User"
    )
