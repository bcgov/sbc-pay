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

"""Mock LDAP Class to be used in unit tests."""
import sys
from collections import defaultdict


class MockLDAP(object):
    """Mock LDAP Class. It just passes everything, no fancy dynamic stuff here!!."""

    def __init__(self):
        """Init."""
        self.directory = defaultdict(lambda: {})

    def set_option(self, option, invalue):
        """Set option value."""

    def initialize(self, uri, trace_level=0, trace_file=sys.stdout, trace_stack_limit=None):
        """Initialize ldap."""

    def simple_bind_s(self, who="", cred=""):
        """Bind."""

    def unbind_s(self):
        """Unbind."""

    def search_s(self, base, scope, filterstr="(objectClass=*)", attrlist=None, attrsonly=0):
        """Search."""
        return "TEST_USER"
