"""Fake OIDC Class.

Create a fake OIDC object for testing.
"""


class FakeOidc:
    """Fake OIDC class."""

    user_loggedin = True

    def user_getfield(self, key):
        """Get user."""
        return "Joe"

    def user_role(self):
        """Get user role."""
        return

    def has_access(self):
        """Check if has access."""
        return True

    def get_access_token(self):
        """Get access token."""
        return "any"

    def _get_token_info(self, token):
        """Get token info."""
        return {"roles": ["admin_view"]}
