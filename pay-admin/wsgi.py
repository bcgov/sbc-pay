# Copyright © 2022 Province of British Columbia
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
"""Provides the WSGI entry point for running the application
"""
from admin import create_app
import sys


# Openshift s2i expects a lower case name of application
application = create_app()  # pylint: disable=invalid-name

if __name__ == "__main__":
    port = '8080'
    if len(sys.argv) > 1:
        port = sys.argv[1]
    application.run(port=int(port), debug=True)
