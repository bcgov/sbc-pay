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
"""Utilities used by the integration tests."""
import json

import stan


async def helper_add_event_to_queue(stan_client: stan.aio.client.Client,
                                    subject: str,
                                    old_identifier: str = 'T1234567890',
                                    new_identifier: str = 'BC1234567890'):
    """Add event to the Queue."""
    payload = {
        'specversion': '1.x-wip',
        'type': 'bc.registry.business.incorporationApplication',
        'source': 'https://api.business.bcregistry.gov.bc.ca/v1/business/BC1234567/filing/12345678',
        'id': 'C234-1234-1234',
        'time': '2020-08-28T17:37:34.651294+00:00',
        'datacontenttype': 'application/json',
        'identifier': new_identifier,
        'tempidentifier': old_identifier,
        'data': {
            'filing': {
                'header': {'filingId': '12345678'},
                'business': {'identifier': 'BC1234567'}
            }
        }
    }

    await stan_client.publish(subject=subject,
                              payload=json.dumps(payload).encode('utf-8'))
