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
import os
from typing import Callable

from stan.aio.client import Client, Msg


async def subscribe_to_queue(stan_client: Client,
                             call_back: Callable[[Msg], None]) \
        -> str:
    """Subscribe to the Queue using the environment setup.

    Args:
        stan_client: the stan connection
        call_back: a callback function that accepts 1 parameter, a Msg
    Returns:
       str: the name of the queue
    """
    entity_subject = os.getenv('NATS_SUBJECT')
    entity_queue = os.getenv('NATS_QUEUE')
    entity_durable_name = entity_queue + '_durable'

    await stan_client.subscribe(subject=entity_subject,
                                queue=entity_queue,
                                durable_name=entity_durable_name,
                                cb=call_back)
    return entity_subject
