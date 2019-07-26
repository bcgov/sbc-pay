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
"""Service class to control all the operations related to Payment."""

import asyncio
import json
import random

from flask import current_app
from nats.aio.client import Client as NATS  # noqa N814; by convention the name is NATS
from stan.aio.client import Client as STAN  # noqa N814; by convention the name is STAN

from pay_api.utils.handlers import error_cb, closed_cb


def publish_response(payload):
    """Publish payment response to async nats."""
    asyncio.run(publish(payload=payload))


async def publish(payload):  # pylint: disable=too-few-public-methods
    """Service to manage Queue publish operations."""
    current_app.logger.debug('<publish')
    # NATS client connections
    nc = NATS()
    sc = STAN()

    async def close():
        """Close the stream and nats connections."""
        await sc.close()
        await nc.close()

    # Connection and Queue configuration.
    def nats_connection_options():
        return {
            'servers': current_app.config.get('NATS_SERVERS'),
            # 'io_loop': loop,
            'error_cb': error_cb,
            'closed_cb': closed_cb,
            'name': current_app.config.get('NATS_CLIENT_NAME'),
        }

    def stan_connection_options():
        return {
            'cluster_id': current_app.config.get('NATS_CLUSTER_ID'),
            'client_id': str(random.SystemRandom().getrandbits(0x58)),
            'nats': nc
        }

    async def ack_handler(ack):
        current_app.logger.debug("Received ack: {}".format(ack.guid))

    try:
        # Connect to the NATS server, and then use that for the streaming connection.
        await nc.connect(**nats_connection_options(), verbose=True, connect_timeout=1, reconnect_time_wait=1)
        await sc.connect(**stan_connection_options())

        current_app.logger.debug(payload)

        await sc.publish(subject=current_app.config.get('NATS_SUBJECT'),
                         payload=json.dumps(payload).encode('utf-8'), ack_handler=ack_handler)

    except Exception as e:  # pylint: disable=broad-except
        current_app.logger.error(e)
        raise
    finally:
        # await nc.flush()
        await close()
    current_app.logger.debug('>publish')
