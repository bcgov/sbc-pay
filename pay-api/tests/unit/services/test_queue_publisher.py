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

"""Tests to assure the Queue integration layer.

Test-Suite to ensure that the Queue publishing is working as expected.
"""
import json
from unittest.mock import patch

import pytest
from flask import current_app
from tests import skip_in_pod

from .utils import subscribe_to_queue


@pytest.mark.asyncio
@skip_in_pod
async def test_publish(app, stan_server, client_id, stan, future, event_loop):
    """Assert that payment tokens can be retrieved and decoded from the Queue."""
    with app.app_context():
        # Call back for the subscription
        async def subscriber_callback(msg):
            current_app.logger.debug('Inside Call Back')
            current_app.logger.debug(msg.data.decode('utf-8'))
            message_dict = json.loads(msg.data.decode('utf-8'))
            assert 'paymentToken' in message_dict
            current_app.logger.debug(message_dict['paymentToken']['statusCode'])
            assert 'COMPLETED' == message_dict['paymentToken']['statusCode']

        await subscribe_to_queue(stan, subscriber_callback)

        # publish message
        from pay_api.services.queue_publisher import publish

        payload = {'paymentToken': {'id': 1, 'statusCode': 'COMPLETED'}}

        await publish(payload=payload)


@pytest.mark.asyncio
@skip_in_pod
async def test_publish_transaction_failed(app, client_id, stan, future, stan_server):
    """Assert that payment tokens can be retrieved and decoded from the Queue."""
    with app.app_context():
        # Call back for the subscription
        async def subscriber_callback(msg):
            current_app.logger.debug('Inside Call Back')
            current_app.logger.debug(msg.data.decode('utf-8'))
            message_dict = json.loads(msg.data.decode('utf-8'))
            assert 'paymentToken' in message_dict
            current_app.logger.debug(message_dict['paymentToken']['statusCode'])
            assert 'TRANSACTION_FAILED' == message_dict['paymentToken']['statusCode']

        await subscribe_to_queue(stan, subscriber_callback)

        # publish message
        from pay_api.services.queue_publisher import publish

        payload = {'paymentToken': {'id': 100, 'statusCode': 'TRANSACTION_FAILED'}}

        await publish(payload=payload)


@pytest.mark.asyncio
@skip_in_pod
async def test_publish_transaction_bulk_load(app, client_id, stan, future, stan_server):
    """Assert that payment tokens can be retrieved and decoded from the Queue."""
    with app.app_context():
        # Call back for the subscription
        async def subscriber_callback(msg):
            current_app.logger.debug('Inside Call Back')
            current_app.logger.debug(msg.data.decode('utf-8'))
            message_dict = json.loads(msg.data.decode('utf-8'))
            assert 'paymentToken' in message_dict
            current_app.logger.debug(message_dict['paymentToken']['statusCode'])
            assert 'COMPLETED' == message_dict['paymentToken']['statusCode']

        await subscribe_to_queue(stan, subscriber_callback)

        # publish message
        from pay_api.services.queue_publisher import publish

        for i in range(10):
            payload = {'paymentToken': {'id': i, 'statusCode': 'COMPLETED'}}
            await publish(payload=payload)


@pytest.mark.asyncio
@skip_in_pod
async def test_publish_transaction_nats_down(app, client_id, stan, future, stan_server):
    """Assert that payment tokens can be retrieved and decoded from the Queue."""
    with app.app_context():
        # Call back for the subscription
        nats_connect = patch('nats.aio.client.Client.connect')

        mock = nats_connect.start()
        mock.side_effect = Exception()

        # publish message
        from pay_api.services.queue_publisher import publish

        payload = {'paymentToken': {'id': 10, 'statusCode': 'COMPLETED'}}
        with pytest.raises(Exception):
            await publish(payload=payload)
        mock.stop()
