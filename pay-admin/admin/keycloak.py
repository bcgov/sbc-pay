"""Copyright 2018 Province of British Columbia.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from flask import redirect, request, session, url_for
import flask_oidc


class Keycloak:
    """Keycloak class establishing OIDC connections.

    Singleton that allows us to create the OIDC once with the application, but then re-use that OIDC without
    re-instantiating.
    """

    _oidc = None

    def __init__(self, application):
        """Initialize the class.

        Only create the oidc object when it is None (prevent duplicate instantiation)
        and the application is defined (allow import prior to instantiation).
        """
        if not Keycloak._oidc and application:
            Keycloak._oidc = flask_oidc.OpenIDConnect(application)

    def is_logged_in(self) -> bool:
        """Determine whether or not the user is logged in."""
        return self._oidc.user_loggedin

    def has_access(self, role='admin_view') -> bool:
        """Determine whether or not the user is authorized to use the application. True if the user have role."""
        if not self._oidc.get_access_token():
            return False

        if not session['oidc_auth_profile']['roles']:
            return False

        roles_ = session['oidc_auth_profile']['roles']
        access = role in roles_

        return access

    def get_redirect_url(self) -> str:
        """
        Get the redirect URL that is used to transfer the browser to the identity provider.

        :rtype: object
        """
        return redirect(url_for('oidc_auth.login', next=request.url))

    def get_username(self) -> str:
        """Get the username for the currently logged in user."""
        return self._oidc.user_getfield('preferred_username')
