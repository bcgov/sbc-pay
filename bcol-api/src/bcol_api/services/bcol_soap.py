# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Holder for SOAP from BCOL."""

import zeep
from flask import current_app


class Singleton(type):
    """Singleton meta."""

    _instances = {}

    def __call__(cls, *args, **kwargs):
        """Call for meta."""
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class BcolSoap(metaclass=Singleton):  # pylint: disable=too-few-public-methods
    """Singleton wrapper for BCOL SOAP."""

    __profile_client = None
    __payment_client = None
    __applied_chg_client = None

    def get_profile_client(self):
        """Retrieve singleton Query Profile Client."""
        return self.__profile_client

    def get_payment_client(self):
        """Retrieve singleton Payment Create Client."""
        return self.__payment_client

    def get_applied_chg_client(self):
        """Retrieve singleton Applied Charge Client."""
        return self.__applied_chg_client

    def __init__(self):
        """Private constructor."""
        self.__profile_client = zeep.Client(current_app.config.get("BCOL_QUERY_PROFILE_WSDL_URL"))

        self.__payment_client = zeep.Client(current_app.config.get("BCOL_PAYMENTS_WSDL_URL"))

        self.__applied_chg_client = zeep.Client(current_app.config.get("BCOL_APPLIED_CHARGE_WSDL_URL"))
