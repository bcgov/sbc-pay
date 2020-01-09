# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""CORS pre-flight decorator.

A simple decorator to add the options method to a Request Class.
"""
from flask import current_app


def cors_preflight(methods: str = 'GET'):
    """Render an option method on the class."""
    def wrapper(f):
        def options(self, *args, **kwargs):  # pylint: disable=unused-argument
            return {'Allow': methods}, 200, \
                   {'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': methods,
                    'Access-Control-Allow-Headers': 'Authorization, Content-Type, registries-trace-id'}

        setattr(f, 'options', options)
        return f

    return wrapper


def is_valid_redirect_url(url: str):
    """Validate if the url is valid based on the VALID Redirect Url."""
    valid_urls: list = current_app.config.get('VALID_REDIRECT_URLS')
    is_valid = False
    for valid_url in valid_urls:
        is_valid = url.startswith(valid_url[:-1]) if valid_url.endswith('*') else valid_url == url
        if is_valid:
            break
    return is_valid


def convert_to_bool(value: str):
    """Convert string to boolean."""
    return value.lower() == 'true'
