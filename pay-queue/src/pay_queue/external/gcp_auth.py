# pylint: skip-file
# flake8: noqa
# This will get moved to an external library, which is linted by black (different than our rules)
"""Move this to external library."""
import functools
from http import HTTPStatus

import google.oauth2.id_token as id_token
from cachecontrol import CacheControl
from flask import abort, current_app, request
from google.auth.transport.requests import Request
from requests.sessions import Session


def verify_jwt(session):
    """Verify token is valid."""
    msg = ''
    try:
        # Get the Cloud Pub/Sub-generated JWT in the "Authorization" header.
        id_token.verify_oauth2_token(
            request.headers.get('Authorization').split()[1],
            Request(session=session),
            audience=current_app.config.get('PAY_SUB_AUDIENCE')
        )
    except Exception as e:  # TODO fix
        msg = f'Invalid token: {e}\n'
    finally:
        return msg


def ensure_authorized_queue_user(f):
    """Ensures the user is authorized to use the queue."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Use CacheControl to avoid re-fetching certificates for every request.
        if message := verify_jwt(CacheControl(Session())):
            print(message)
            abort(HTTPStatus.UNAUTHORIZED)
        return f(*args, **kwargs)
    return decorated_function
