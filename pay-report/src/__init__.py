"""Source package - automatically enforces authentication on import."""

from . import auth

# Enforce authentication globally when src package is imported
# This ensures all pages that import from src are protected
# We also use decorators on database connection functions to enforce authentication.
auth.enforce_auth()
