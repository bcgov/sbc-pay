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
"""The configuration for gunicorn, which picks up the
   runtime options from environment variables
"""

import os


workers = int(os.environ.get('GUNICORN_PROCESSES', '3'))
worker_class = os.environ.get('GUNICORN_WORKER_CLASS', 'gevent')
worker_connections = int(os.environ.get('GUNICORN_WORKER_CONNECIONS', '1000'))
threads = int(os.environ.get('GUNICORN_THREADS', '1'))
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '60'))
keepalive = int(os.environ.get('GUNICORN_KEEPALIVE', '2'))


forwarded_allow_ips = '*'  # pylint: disable=invalid-name
secure_scheme_headers = {'X-Forwarded-Proto': 'https'}  # pylint: disable=invalid-name
