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
import json
import jwt
from urllib.request import urlopen
from cachelib import SimpleCache
from flask import abort, current_app, redirect, request, url_for
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

        self.cache = SimpleCache(default_timeout=300)

    def is_logged_in(self) -> bool:
        """Determine whether or not the user is logged in."""
        return self._oidc.user_loggedin

    def _get_jwks_from_cache(self):
        jwks = self.cache.get('jwks')
        if jwks is None:
            jwks = self._fetch_jwks_from_url()
            self.cache.set('jwks', jwks)
        return jwks

    def _fetch_jwks_from_url(self):
        jwks_uri = current_app.config.get('JWT_OIDC_JWKS_URI', None)
        if not jwks_uri:
            abort(500, 'JWT_OIDC_JWKS_URI is not configured')
        return json.loads(urlopen(jwks_uri).read().decode('utf-8'))

    def has_access(self, role='admin_view') -> bool:
        """Determine whether or not the user is authorized to use the application. True if the user have role."""
        if not (token := self._oidc.get_access_token()):
            return False

        public_keys = {}
        for jwk in self._get_jwks_from_cache().get('keys'):
            public_keys[jwk['kid']] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

        key = public_keys[jwt.get_unverified_header(token)['kid']]
        token_info = jwt.decode(token, key=key, audience=current_app.config.get('JWT_AUDIENCE'), algorithms=['RS256'])
        if not token_info['roles']:
            return False

        roles_ = token_info['roles']
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
